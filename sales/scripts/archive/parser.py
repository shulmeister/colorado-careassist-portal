import pdfplumber
import pytesseract
import re
import io
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from PIL import Image, ImageOps, ImageFilter
from pytesseract import Output
import hashlib

logger = logging.getLogger(__name__)

try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # type: ignore
    logger.warning("NumPy not available, PDF OCR preprocessing will be limited")

try:
    import cv2  # type: ignore
    PDF_OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    PDF_OPENCV_AVAILABLE = False
    logger.warning("OpenCV not available for PDF preprocessing, falling back to PIL")

try:
    import easyocr  # type: ignore
    PDF_EASY_OCR_AVAILABLE = True
except ImportError:
    easyocr = None  # type: ignore
    PDF_EASY_OCR_AVAILABLE = False

try:
    from rapidocr_onnxruntime import RapidOCR  # type: ignore
    PDF_RAPID_OCR_AVAILABLE = True
except ImportError:
    RapidOCR = None  # type: ignore
    PDF_RAPID_OCR_AVAILABLE = False

class PDFParser:
    """Parse MyWay route PDFs and Time tracking PDFs to extract visit information or hours worked"""
    
    def __init__(self):
        # Known healthcare facilities in Colorado Springs area
        self.known_facilities = {
            "uchealth memorial hospital": "UCHealth Memorial Hospital Central",
            "uchealth memorial": "UCHealth Memorial Hospital Central",
            "memorial hospital": "UCHealth Memorial Hospital Central",
            "pikes peak hospice": "Pikes Peak Hospice",
            "independence center": "The Independence Center",
            "penrose hospital": "Penrose Hospital",
            "centura health": "Centura Health",
            "st francis medical center": "St. Francis Medical Center",
            "children's hospital colorado": "Children's Hospital Colorado",
            "peaks recovery center": "Peaks Recovery Center",
            "cedar springs hospital": "Cedar Springs Hospital",
            "parkview medical center": "Parkview Medical Center",
            "st mary corwin": "St. Mary-Corwin Medical Center",
            "healthsouth": "HealthSouth Rehabilitation Hospital",
            "kindred hospital": "Kindred Hospital",
            "rehabilitation hospital": "Rehabilitation Hospital",
            "veterans affairs": "VA Medical Center",
            "va hospital": "VA Medical Center",
            "mountain view medical": "Mountain View Medical Center",
            "peak vista": "Peak Vista Community Health Centers",
            "community health": "Community Health Centers",
            "primary care": "Primary Care Clinic",
            "urgent care": "Urgent Care Center",
            "emergency room": "Emergency Room",
            "er": "Emergency Room"
        }
        
        # Common address patterns
        self.address_patterns = [
            r'\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ln|Lane|Ct|Court|Pl|Place)',
            r'\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ln|Lane|Ct|Court|Pl|Place),\s*Colorado Springs',
            r'\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ln|Lane|Ct|Court|Pl|Place),\s*CO'
        ]
        
        self._vowel_set = set("aeiouAEIOU")
        self._common_terms = {
            "total", "hours", "visit", "stop", "address", "facility", "phone", "email",
            "driver", "route", "notes", "mileage", "arrival", "departure", "patient",
            "care", "manager", "center", "clinic", "hospital", "pueblo", "denver",
            "colorado", "springs", "time", "sheet", "lunch", "break"
        }
        self._easyocr_reader = None
        self._rapidocr_reader = None
    
    def _clean_extracted_text(self, text: str) -> str:
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            lines.append(' '.join(line.split()))
        return '\n'.join(lines)

    def _post_process_text(self, text: str) -> str:
        if not text:
            return ""
        filtered_lines: List[str] = []
        fallback_lines: List[str] = []
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            fallback_lines.append(stripped)
            if self._text_is_meaningful(stripped, threshold=0.22) or re.search(r'\d{2,}', stripped):
                filtered_lines.append(stripped)
        if filtered_lines:
            return '\n'.join(filtered_lines)
        return '\n'.join(fallback_lines)
    
    def _score_text(self, text: str) -> float:
        if not text:
            return 0.0
        
        stripped = ''.join(ch for ch in text if ch.isprintable())
        if not stripped:
            return 0.0
        
        letters = sum(1 for ch in stripped if ch.isalpha())
        digits = sum(1 for ch in stripped if ch.isdigit())
        spaces = sum(1 for ch in stripped if ch.isspace())
        punctuation = len(stripped) - letters - digits - spaces
        length = len(stripped)
        if length == 0:
            return 0.0
        
        base_score = (letters + 0.6 * digits + 0.25 * punctuation) / length
        
        words = [word for word in re.findall(r"[A-Za-z]+", stripped) if len(word) > 1]
        if not words:
            return 0.15 * base_score
        
        vowel_words = sum(1 for word in words if any(ch in self._vowel_set for ch in word))
        vowel_ratio = vowel_words / len(words)
        if vowel_ratio < 0.3:
            base_score *= 0.35
        else:
            base_score *= 1.05
        
        avg_word_length = sum(len(word) for word in words) / len(words)
        if avg_word_length < 2.3:
            base_score *= 0.45
        elif avg_word_length > 11:
            base_score *= 0.7
        
        common_hits = sum(1 for word in words if word.lower() in self._common_terms)
        if common_hits:
            base_score += min(common_hits, 5) * 0.07
        
        if '@' in stripped:
            base_score += 0.3
        if any(keyword in stripped.lower() for keyword in ['visit', 'hours', 'total', 'route', 'stop']):
            base_score += 0.15
        
        unique_chars = len(set(stripped))
        if unique_chars <= length * 0.25:
            base_score *= 0.5
        
        return min(base_score, 2.0)
    
    def _text_is_meaningful(self, text: str, threshold: float = 0.22) -> bool:
        return self._score_text(text) >= threshold
    
    def _prepare_pdf_variants(self, image: Image.Image) -> List[Image.Image]:
        variants: List[Image.Image] = []
        try:
            rgb_image = image.convert("RGB")
        except Exception:
            rgb_image = image
        
        variants.append(rgb_image)
        gray = rgb_image.convert("L")
        variants.append(ImageOps.autocontrast(gray))
        variants.append(ImageOps.invert(ImageOps.autocontrast(gray)))
        variants.append(gray.filter(ImageFilter.MedianFilter(size=3)))
        
        if PDF_OPENCV_AVAILABLE and np is not None and cv2 is not None:
            try:
                gray_np = np.array(gray)
                denoised = cv2.fastNlMeansDenoising(gray_np, None, 20, 7, 21)
                adaptive = cv2.adaptiveThreshold(
                    denoised,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    29,
                    4
                )
                otsu_blur = cv2.GaussianBlur(denoised, (5, 5), 0)
                _, otsu = cv2.threshold(otsu_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                variants.append(Image.fromarray(adaptive))
                variants.append(Image.fromarray(otsu))
            except Exception as exc:
                logger.debug("OpenCV preprocessing for PDF failed: %s", exc)
        
        unique_variants: List[Image.Image] = []
        seen_hashes = set()
        for variant in variants:
            if variant is None:
                continue
            try:
                fingerprint = variant.tobytes()
            except Exception:
                unique_variants.append(variant)
                continue
            hash_value = hashlib.md5(fingerprint).hexdigest()
            if hash_value not in seen_hashes:
                seen_hashes.add(hash_value)
                unique_variants.append(variant)
        
        return unique_variants
    
    def _extract_high_conf_data(self, image: Image.Image, config: str) -> Tuple[str, float]:
        try:
            ocr_data = pytesseract.image_to_data(
                image,
                config=config,
                lang="eng",
                output_type=Output.DICT
            )
        except Exception as exc:
            logger.debug("image_to_data failed for PDF OCR: %s", exc)
            return "", 0.0
        
        line_map: Dict[Tuple[int, int, int], List[str]] = {}
        conf_map: Dict[Tuple[int, int, int], List[float]] = {}
        
        for idx, word in enumerate(ocr_data.get("text", [])):
            try:
                conf = float(ocr_data.get("conf", [])[idx])
            except (ValueError, TypeError, IndexError):
                conf = -1.0
            if conf < 58:
                continue
            cleaned = word.strip()
            if not cleaned:
                continue
            key = (
                ocr_data.get("block_num", [0])[idx] if idx < len(ocr_data.get("block_num", [])) else 0,
                ocr_data.get("par_num", [0])[idx] if idx < len(ocr_data.get("par_num", [])) else 0,
                ocr_data.get("line_num", [idx])[idx] if idx < len(ocr_data.get("line_num", [])) else idx
            )
            line_map.setdefault(key, []).append(cleaned)
            conf_map.setdefault(key, []).append(conf)
        
        if not line_map:
            return "", 0.0
        
        reconstructed_lines: List[str] = []
        confidences: List[float] = []
        
        for key, words in sorted(line_map.items(), key=lambda item: item[0]):
            if not words:
                continue
            line_text = self._clean_extracted_text(' '.join(words))
            if not line_text:
                continue
            avg_conf = sum(conf_map.get(key, [])) / max(len(conf_map.get(key, [])), 1) if conf_map.get(key) else 0.0
            if not self._text_is_meaningful(line_text, threshold=0.18) and avg_conf < 70:
                continue
            reconstructed_lines.append(line_text)
            confidences.append(avg_conf)
        
        if not reconstructed_lines:
            return "", 0.0
        
        avg_confidence = sum(confidences) / max(len(confidences), 1)
        combined_text = '\n'.join(reconstructed_lines)
        processed_text = self._post_process_text(combined_text)
        final_text = processed_text if processed_text else combined_text
        return final_text, avg_confidence
    
    def _ocr_with_tesseract_variants(self, variants: List[Image.Image]) -> List[Tuple[float, str]]:
        configs = [
            ("psm6", '--oem 3 --psm 6 --dpi 320 -c preserve_interword_spaces=1'),
            ("psm11", '--oem 3 --psm 11 --dpi 320'),
            ("psm4", '--oem 3 --psm 4 --dpi 320'),
            ("psm12", '--oem 3 --psm 12 --dpi 320'),
        ]
        
        results: List[Tuple[float, str]] = []
        seen_texts = set()
        
        for variant_index, variant in enumerate(variants):
            for config_name, config in configs:
                try:
                    raw_text = pytesseract.image_to_string(variant, config=config, lang="eng")
                    cleaned = self._clean_extracted_text(raw_text)
                    filtered = self._post_process_text(cleaned)
                    candidate_text = filtered if filtered else cleaned
                    if candidate_text and candidate_text not in seen_texts:
                        score = self._score_text(candidate_text)
                        if score >= 0.18:
                            results.append((score, candidate_text))
                            seen_texts.add(candidate_text)
                        logger.info(
                            "PDF OCR (%s variant %d) extracted %d chars (score %.3f)",
                            config_name,
                            variant_index,
                            len(candidate_text),
                            score
                        )
                    
                    data_text, avg_conf = self._extract_high_conf_data(variant, config)
                    if data_text and data_text not in seen_texts:
                        processed_data_text = self._post_process_text(data_text)
                        useful_text = processed_data_text if processed_data_text else data_text
                        data_score = self._score_text(useful_text)
                        combined_score = max(data_score, (avg_conf / 100.0) + 0.1)
                        if combined_score >= 0.18:
                            results.append((combined_score, useful_text))
                            seen_texts.add(useful_text)
                        logger.info(
                            "PDF OCR data (%s variant %d) extracted %d chars (avg conf %.1f, score %.3f)",
                            config_name,
                            variant_index,
                            len(useful_text),
                            avg_conf,
                            combined_score
                        )
                except Exception as exc:
                    logger.debug("Tesseract OCR failed (%s variant %d): %s", config_name, variant_index, exc)
        
        return results
    
    def _merge_text_blocks(self, base_text: str, new_text: str) -> str:
        if not new_text:
            return base_text
        
        base_lines = [line.strip() for line in base_text.split('\n') if line.strip()]
        seen_lines = set(base_lines)
        
        for line in new_text.split('\n'):
            line = line.strip()
            if not line or line in seen_lines:
                continue
            if not self._text_is_meaningful(line, threshold=0.18):
                continue
            base_lines.append(line)
            seen_lines.add(line)
        
        return '\n'.join(base_lines)
    
    def _get_easyocr_reader(self):
        if not PDF_EASY_OCR_AVAILABLE:
            return None
        if self._easyocr_reader is not None:
            return self._easyocr_reader
        if np is None:
            return None
        try:
            self._easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            logger.info("EasyOCR reader initialized for PDF parsing")
        except Exception as exc:
            logger.warning("Failed to initialize EasyOCR reader for PDFs: %s", exc)
            self._easyocr_reader = None
        return self._easyocr_reader
    
    def _easyocr_fallback(self, image: Image.Image) -> str:
        reader = self._get_easyocr_reader()
        if reader is None or np is None:
            return ""
        try:
            results = reader.readtext(np.array(image.convert("RGB")), detail=0, paragraph=True)
            cleaned = self._clean_extracted_text('\n'.join(result for result in results if isinstance(result, str)))
            if cleaned:
                logger.info("EasyOCR fallback for PDF produced %d characters", len(cleaned))
            return cleaned
        except Exception as exc:
            logger.warning("EasyOCR fallback for PDF failed: %s", exc)
            return ""
    
    def _get_rapidocr_reader(self):
        if not PDF_RAPID_OCR_AVAILABLE:
            return None
        if self._rapidocr_reader is not None:
            return self._rapidocr_reader
        if np is None:
            return None
        try:
            self._rapidocr_reader = RapidOCR()
            logger.info("RapidOCR reader initialized for PDF parsing")
        except Exception as exc:
            logger.warning("Failed to initialize RapidOCR reader for PDFs: %s", exc)
            self._rapidocr_reader = None
        return self._rapidocr_reader

    def _rapidocr_fallback(self, image: Image.Image) -> str:
        reader = self._get_rapidocr_reader()
        if reader is None or np is None:
            return ""
        try:
            result, _ = reader(np.array(image.convert("RGB")))
        except Exception as exc:
            logger.warning("RapidOCR fallback for PDF failed: %s", exc)
            return ""
        if not result:
            return ""
        lines: List[str] = []
        for entry in result:
            if not isinstance(entry, (list, tuple)) or len(entry) < 3:
                continue
            text = entry[1]
            score = entry[2]
            if text is None:
                continue
            try:
                score_value = float(score)
            except (TypeError, ValueError):
                score_value = 0.0
            if score_value < 0.45:
                continue
            cleaned = self._clean_extracted_text(text)
            if cleaned:
                lines.append(cleaned)
        combined = '\n'.join(lines)
        return self._post_process_text(combined)
    
    def _extract_text_from_page(self, page, min_text_length: int = 40) -> str:
        """Extract text from a pdfplumber page, falling back to OCR when necessary"""
        try:
            page_text = page.extract_text() or ""
            cleaned_text = self._clean_extracted_text(page_text)
            if cleaned_text and len(cleaned_text) >= min_text_length and self._text_is_meaningful(cleaned_text):
                return cleaned_text
        except Exception as e:
            logger.debug(f"pdfplumber extract_text failed on page {getattr(page, 'page_number', '?')}: {str(e)}")
            cleaned_text = ""
        
        # Fallback to OCR if direct extraction failed or produced too little text
        page_image = None
        try:
            page_number = getattr(page, "page_number", "?")
            page_image = page.to_image(resolution=300)
            pil_image = page_image.original.convert("RGB")
            variants = self._prepare_pdf_variants(pil_image)
            ocr_results = self._ocr_with_tesseract_variants(variants)
            if ocr_results:
                ocr_results.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
                best_score, best_text = ocr_results[0]
                combined_text = best_text
                for score, text in ocr_results[1:]:
                    if score < max(best_score - 0.15, 0.2):
                        continue
                    combined_text = self._merge_text_blocks(combined_text, text)
                filtered_text = self._post_process_text(combined_text)
                if filtered_text:
                    combined_text = filtered_text
                    best_score = self._score_text(combined_text)
                logger.info(
                    "OCR fallback extracted %d characters from page %s (score %.3f)",
                    len(combined_text),
                    page_number,
                    best_score
                )
                if (best_score < 0.4 or len(combined_text) < 80) and PDF_RAPID_OCR_AVAILABLE:
                    rapid_text = self._rapidocr_fallback(pil_image)
                    if rapid_text:
                        rapid_score = self._score_text(rapid_text)
                        if rapid_score > best_score:
                            logger.info(
                                "RapidOCR fallback improved page %s score from %.3f to %.3f",
                                page_number,
                                best_score,
                                rapid_score
                            )
                            return rapid_text
                return combined_text
            
            easy_text = self._easyocr_fallback(pil_image)
            if easy_text and self._text_is_meaningful(easy_text, threshold=0.2):
                easy_text_filtered = self._post_process_text(easy_text)
                if easy_text_filtered:
                    easy_text = easy_text_filtered
                logger.info(
                    "EasyOCR fallback extracted %d characters from page %s",
                    len(easy_text),
                    page_number
                )
                if (self._score_text(easy_text) < 0.4 or len(easy_text) < 80) and PDF_RAPID_OCR_AVAILABLE:
                    rapid_text = self._rapidocr_fallback(pil_image)
                    if rapid_text and self._score_text(rapid_text) > self._score_text(easy_text):
                        return rapid_text
                return easy_text
            
            if PDF_RAPID_OCR_AVAILABLE:
                rapid_text = self._rapidocr_fallback(pil_image)
                if rapid_text:
                    return rapid_text
        except Exception as ocr_error:
            logger.warning(f"OCR fallback failed on page {getattr(page, 'page_number', '?')}: {str(ocr_error)}")
        finally:
            if page_image is not None:
                try:
                    page_image.close()
                except Exception:
                    pass
        
        return cleaned_text.strip()
    
    def detect_pdf_type(self, pdf_content: bytes) -> str:
        """Detect if PDF is a MyWay route or Time tracking document"""
        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                # Get text from first few pages
                text = ""
                for page_num, page in enumerate(pdf.pages[:3]):  # Check first 3 pages
                    page_text = self._extract_text_from_page(page, min_text_length=20)
                    if page_text:
                        text += page_text.lower()
                
                # Look for time tracking indicators
                time_indicators = [
                    "time tracking", "hours worked", "daily hours", "total hours",
                    "clock in", "clock out", "break", "lunch", "start time", "end time",
                    "time sheet", "timesheet", "work log", "daily log"
                ]
                
                # Look for MyWay route indicators
                route_indicators = [
                    "myway", "route", "stop", "visits", "delivery", "pickup",
                    "address", "location", "business", "facility"
                ]
                
                time_score = sum(1 for indicator in time_indicators if indicator in text)
                route_score = sum(1 for indicator in route_indicators if indicator in text)
                
                logger.info(f"PDF type detection - Time indicators: {time_score}, Route indicators: {route_score}")
                
                if time_score > route_score and time_score > 0:
                    return "time_tracking"
                else:
                    return "myway_route"
                    
        except Exception as e:
            logger.error(f"Error detecting PDF type: {str(e)}")
            return "myway_route"  # Default to route parsing
    
    def parse_pdf(self, pdf_content: bytes) -> Dict[str, Any]:
        """Parse PDF content and return appropriate data based on PDF type"""
        pdf_type = self.detect_pdf_type(pdf_content)
        
        if pdf_type == "time_tracking":
            return self.parse_time_tracking_pdf(pdf_content)
        else:
            return self.parse_myway_route_pdf(pdf_content)
    
    def parse_time_tracking_pdf(self, pdf_content: bytes) -> Dict[str, Any]:
        """Parse time tracking PDF to extract daily hours worked"""
        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                text = ""
                for page_index, page in enumerate(pdf.pages):
                    page_text = self._extract_text_from_page(page)
                    if page_text:
                        text += page_text + "\n"
                
                # Extract date and total hours
                date, total_hours = self._extract_time_data(text)
                
                logger.info(f"Extracted time data - Date: {date}, Hours: {total_hours}")
                
                return {
                    "type": "time_tracking",
                    "date": date,
                    "total_hours": total_hours,
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"Error parsing time tracking PDF: {str(e)}")
            return {
                "type": "time_tracking",
                "success": False,
                "error": str(e)
            }
    
    def _extract_time_data(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """Extract date and total hours from time tracking text"""
        date = None
        total_hours = None
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Look for date patterns (MM/DD/YYYY, MM-DD-YYYY, etc.)
            date_patterns = [
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
                r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and not date:
                    date = match.group(1)
                    break
            
            # Look for total hours patterns
            hours_patterns = [
                r'total[:\s]+(\d+\.?\d*)\s*hours?',
                r'hours?[:\s]+(\d+\.?\d*)',
                r'total[:\s]+(\d+\.?\d*)',
                r'(\d+\.?\d*)\s*hours?',
            ]
            
            for pattern in hours_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and not total_hours:
                    try:
                        total_hours = float(match.group(1))
                        break
                    except ValueError:
                        continue
        
        return date, total_hours
    
    def parse_myway_route_pdf(self, pdf_content: bytes) -> Dict[str, Any]:
        """Parse MyWay route PDF content and extract visit information"""
        try:
            visits = []
            pdf_date = None
            total_mileage = None
            
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                page_texts: List[str] = []
                for page in pdf.pages:
                    page_texts.append(self._extract_text_from_page(page))
                
                # Extract date from first page
                if page_texts:
                    first_page_text = page_texts[0]
                    if first_page_text:
                        pdf_date = self._extract_date_from_text(first_page_text)
                        if not pdf_date:
                            # Try full PDF text if not found on first page
                            full_text = "\n".join(page_texts[:3])  # Use first three pages
                            pdf_date = self._extract_date_from_text(full_text)
                
                # Combine all text to search for global stats like mileage
                full_text = "\n".join(page_texts)
                total_mileage = self._extract_mileage_from_text(full_text)
                
                # Extract visits from all pages
                for page_num, text in enumerate(page_texts):
                    if text:
                        page_visits = self._extract_visits_from_text(text, page_num + 1, pdf_date)
                        visits.extend(page_visits)
            
            # Clean and validate visits
            cleaned_visits = self._clean_visits(visits)
            
            logger.info(f"Extracted {len(cleaned_visits)} visits from MyWay route PDF. Mileage: {total_mileage}")
            
            return {
                "type": "myway_route",
                "visits": cleaned_visits,
                "count": len(cleaned_visits),
                "mileage": total_mileage,
                "date": pdf_date,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error parsing MyWay route PDF: {str(e)}")
            return {
                "type": "myway_route",
                "success": False,
                "error": str(e)
            }
    
    def _extract_mileage_from_text(self, text: str) -> Optional[float]:
        """Extract total mileage from text"""
        # Patterns for mileage (e.g. "Total Miles: 45.2", "Mileage: 120")
        mileage_patterns = [
            r'(?:Total\s+)?Miles[:\s]+(\d+\.?\d*)',
            r'Mileage[:\s]+(\d+\.?\d*)',
            r'Distance[:\s]+(\d+\.?\d*)\s*mi',
            r'(\d+\.?\d*)\s*miles\s+driven',
            r'Total\s+Distance[:\s]+(\d+\.?\d*)'
        ]
        
        for pattern in mileage_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None

    def _extract_visits_from_text(self, text: str, page_num: int, pdf_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Extract visit information from page text"""
        visits = []
        lines = text.split('\n')
        
        current_stop = None
        current_address = None
        current_notes = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Look for stop numbers
            stop_match = re.search(r'^(\d+)[\.\)\-\s]', line)
            if stop_match:
                # Save previous visit if exists (FIX: removed duplicate visit creation)
                if current_stop is not None:
                    visit = self._create_visit(current_stop, current_address, current_notes, page_num, pdf_date)
                    if visit:
                        visits.append(visit)
                
                # Start new visit
                current_stop = int(stop_match.group(1))
                current_address = None
                current_notes = []
                
                # Extract address from the same line or next lines
                remaining_text = line[stop_match.end():].strip()
                address = self._extract_address(remaining_text)
                if address:
                    current_address = address
                else:
                    # Look in next few lines for address
                    for j in range(i+1, min(i+3, len(lines))):
                        address = self._extract_address(lines[j])
                        if address:
                            current_address = address
                            break
            
            # Look for addresses in non-stop lines
            elif current_stop is not None and not current_address:
                address = self._extract_address(line)
                if address:
                    current_address = address
            
            # Collect notes
            elif current_stop is not None:
                # Skip common non-note patterns
                if not re.match(r'^(Route|Stop|Time|Date|Driver|Vehicle)', line, re.IGNORECASE):
                    current_notes.append(line)
        
        # Don't forget the last visit
        if current_stop is not None:
            visit = self._create_visit(current_stop, current_address, current_notes, page_num, pdf_date)
            if visit:
                visits.append(visit)
        
        return visits
    
    def _extract_address(self, text: str) -> Optional[str]:
        """Extract address from text"""
        for pattern in self.address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None
    
    def _extract_city_from_address(self, address: str, notes: List[str]) -> str:
        """Extract city from address or notes - prioritize address/notes, add Denver street detection"""
        # Common Colorado cities
        cities = ["Denver", "Colorado Springs", "Pueblo", "Aurora", "Fort Collins", 
                 "Lakewood", "Thornton", "Arvada", "Westminster", "Centennial",
                 "Boulder", "Greeley", "Longmont", "Loveland", "Grand Junction",
                 "Broomfield", "Commerce City", "Northglenn", "Parker", "Castle Rock",
                 "Fountain", "Monument", "Manitou Springs"]
        
        # Denver street names (these indicate Denver, not Colorado Springs)
        denver_streets = [
            "iliff", "cornell", "yale", "jewell", "hampden", "evans", "alameda",
            "mississippi", "louisiana", "colorado blvd", "broadway", "downing",
            "humboldt", "logan", "speer", "federal", "colfax", "leetsdale",
            "hampton", "franklin", "park", "washington", "tremont", "monaco",
            "tower", "quebec", "dahlia", "fairfax", "oneida", "syracuse"
        ]
        
        combined_text = f"{address} {' '.join(notes)}".lower()
        
        # FIRST: Check for Denver street names (highest priority - these are definitive)
        for street in denver_streets:
            if street in combined_text:
                return "Denver"
        
        # SECOND: Search for city names in address (more reliable)
        address_lower = address.lower() if address else ""
        for city in cities:
            if city.lower() in address_lower:
                return city
        
        # THIRD: Search in notes
        notes_text = " ".join(notes).lower()
        for city in cities:
            if city.lower() in notes_text:
                return city
        
        # FOURTH: Try to extract city from address pattern (address, city, state)
        # Pattern: "123 Main St, City Name, CO" or "123 Main St, City Name"
        if address:
            city_pattern = r',\s*([A-Za-z\s]+?)(?:,\s*(?:CO|Colorado))?\s*$'
            match = re.search(city_pattern, address, re.IGNORECASE)
            if match:
                extracted_city = match.group(1).strip()
                # Validate it's actually a city name (not a street suffix)
                if extracted_city and len(extracted_city) > 2:
                    # Check if it matches a known city
                    for city in cities:
                        if city.lower() == extracted_city.lower():
                            return city
                    # Return the extracted city if it looks valid
                    if len(extracted_city.split()) <= 3:  # City names are usually 1-3 words
                        return extracted_city.title()
        
        # No city found - return empty string instead of defaulting
        return ""
    
    def _extract_date_from_text(self, text: str) -> Optional[datetime]:
        """Extract date from PDF text"""
        lines = text.split('\n')
        
        # Date patterns to look for
        date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',  # MM/DD/YYYY or MM-DD-YYYY
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',  # YYYY/MM/DD or YYYY-MM-DD
            r'([A-Za-z]+\s+\d{1,2},\s+\d{4})',  # Month DD, YYYY
            r'([A-Za-z]+\s+\d{1,2}[/-]\d{4})',  # Month DD/YYYY
        ]
        
        # Look for dates in first 20 lines (usually in header)
        for line in lines[:20]:
            line = line.strip()
            for pattern in date_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    try:
                        # Try different date formats
                        for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%Y/%m/%d', 
                                   '%B %d, %Y', '%b %d, %Y', '%B %d/%Y', '%b %d/%Y']:
                            try:
                                parsed_date = datetime.strptime(date_str, fmt)
                                # Ensure date is at midnight (no time component) to avoid timezone issues
                                parsed_date = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
                                # Don't use dates that are clearly wrong (too far in future or past)
                                current_year = datetime.now().year
                                if 2020 <= parsed_date.year <= current_year + 1:
                                    logger.info(f"Extracted date from PDF: {parsed_date.date()}")
                                    return parsed_date
                            except ValueError:
                                continue
                    except:
                        continue
        
        return None
    
    def _create_visit(self, stop_num: int, address: str, notes: List[str], page_num: int, pdf_date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Create a visit record"""
        if not address:
            logger.warning(f"Stop {stop_num} on page {page_num} has no address, skipping")
            return None
        
        # Infer business name
        business_name = self._infer_business_name(address, notes)
        
        # Extract city from address (don't default to Colorado Springs)
        city = self._extract_city_from_address(address, notes)
        
        # Clean up address
        clean_address = self._clean_address(address)
        
        # Combine notes
        combined_notes = " ".join(notes).strip()
        
        return {
            "stop_number": stop_num,
            "business_name": business_name,
            "address": clean_address,
            "city": city,
            "notes": combined_notes,
            "visit_date": pdf_date  # Pass date through
        }
    
    def _infer_business_name(self, address: str, notes: List[str]) -> str:
        """Infer business name from address and notes"""
        text_to_search = f"{address} {' '.join(notes)}".lower()
        
        # Check against known facilities
        for keyword, facility_name in self.known_facilities.items():
            if keyword in text_to_search:
                return facility_name
        
        # Try to extract from notes
        for note in notes:
            note_lower = note.lower()
            for keyword, facility_name in self.known_facilities.items():
                if keyword in note_lower:
                    return facility_name
        
        # Enhanced business name extraction from address
        business_name = self._extract_business_name_from_address(address, notes)
        if business_name and business_name != "Healthcare Facility":
            return business_name
        
        # Try extracting business name from address line itself
        # Look for patterns like "Business Name, 123 Main St" or "Business Name - 123 Main St"
        name_patterns = [
            r'^([^,]+?),\s*\d+',  # Name before comma and number
            r'^([^-\d]+?)\s*[-–]\s*\d+',  # Name before dash and number
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+?)\s+(?:at|@)\s+\d+',  # Name before "at" and number
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, address, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                # Validate it looks like a business name (not just street name)
                if len(potential_name) > 5 and not re.search(r'\b(st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive)\b', potential_name, re.IGNORECASE):
                    # Check if it contains healthcare keywords
                    if any(keyword in potential_name.lower() for keyword in ['health', 'medical', 'care', 'hospital', 'clinic', 'center']):
                        return potential_name
                    # Or if it's a multi-word capitalized name (likely business name)
                    words = potential_name.split()
                    if len(words) >= 2 and all(word[0].isupper() for word in words if word):
                        return potential_name
        
        # For MyWay routes, try to infer from street names + context
        street_name = self._extract_street_name(address)
        if street_name:
            # Look for healthcare context in notes
            healthcare_context = self._find_healthcare_context(notes)
            if healthcare_context:
                return f"{street_name} {healthcare_context}"
            else:
                # For MyWay routes, create more descriptive names based on street patterns
                if street_name.lower() in ['monaco', 'arkansas', 'morrison', 'lowell', 'downing', 'harrison', 'first', 'mississippi']:
                    # These are common healthcare facility streets in Colorado Springs
                    return f"{street_name} Healthcare Center"
                else:
                    return f"{street_name} Healthcare Facility"
        
        # Default fallback
        return "Healthcare Facility"
    
    def _extract_business_name_from_address(self, address: str, notes: List[str]) -> str:
        """Extract business name from address using enhanced logic"""
        # Common patterns for healthcare facilities
        healthcare_patterns = [
            r'(\w+(?:\s+\w+)*)\s+(?:Hospital|Medical Center|Health Center|Healthcare Center)',
            r'(\w+(?:\s+\w+)*)\s+(?:Care Center|Rehabilitation Center|Rehab Center)',
            r'(\w+(?:\s+\w+)*)\s+(?:Assisted Living|Senior Living|Memory Care)',
            r'(\w+(?:\s+\w+)*)\s+(?:Hospice|Palliative Care)',
            r'(\w+(?:\s+\w+)*)\s+(?:Clinic|Medical Clinic|Health Clinic)',
            r'(\w+(?:\s+\w+)*)\s+(?:Emergency Room|ER|Emergency Department)',
            r'(\w+(?:\s+\w+)*)\s+(?:Recovery|Treatment Center)',
            r'(\w+(?:\s+\w+)*)\s+(?:Internal Medicine|Family Medicine)',
            r'(\w+(?:\s+\w+)*)\s+(?:Post Acute|Skilled Nursing)',
            r'(\w+(?:\s+\w+)*)\s+(?:Health Care|Healthcare)',
        ]
        
        # Try to match patterns in address
        for pattern in healthcare_patterns:
            match = re.search(pattern, address, re.IGNORECASE)
            if match:
                name_part = match.group(1).strip()
                if len(name_part) > 2 and not name_part.lower() in ['the', 'at', 'of', 'and']:
                    return name_part
        
        # Look for capitalized words that might be business names
        # Split address and look for meaningful capitalized sequences
        address_parts = address.split(',')[0].split()  # Take only street address part
        
        # Find sequences of capitalized words
        capitalized_words = []
        for part in address_parts:
            if part[0].isupper() and len(part) > 2 and not part.lower() in ['st', 'street', 'ave', 'avenue', 'blvd', 'boulevard', 'rd', 'road', 'dr', 'drive', 'ln', 'lane', 'ct', 'court', 'pl', 'place', 'way']:
                capitalized_words.append(part)
            elif capitalized_words:  # Stop if we hit a non-capitalized word after finding some
                break
        
        if capitalized_words:
            # Join capitalized words to form business name
            business_name = " ".join(capitalized_words)
            if len(business_name) > 3:
                # Check if this looks like a street name rather than a business name
                # Street names are usually single words or very short phrases
                if len(capitalized_words) == 1 and len(business_name) < 10:
                    # This is likely a street name, not a business name
                    return None
                return business_name
        
        # Try to extract from notes if available
        for note in notes:
            note_lower = note.lower()
            if any(term in note_lower for term in ['hospital', 'medical', 'health', 'clinic', 'center', 'care']):
                # Look for capitalized words in notes
                note_words = note.split()
                cap_words = [word for word in note_words if word[0].isupper() and len(word) > 2]
                if cap_words:
                    return " ".join(cap_words[:3])  # Take first 3 capitalized words
        
        return None
    
    def _clean_address(self, address: str) -> str:
        """Clean and normalize address"""
        # Remove extra whitespace
        address = re.sub(r'\s+', ' ', address.strip())
        
        # Standardize street abbreviations
        replacements = {
            r'\bSt\b': 'St',
            r'\bStreet\b': 'St',
            r'\bAve\b': 'Ave',
            r'\bAvenue\b': 'Ave',
            r'\bBlvd\b': 'Blvd',
            r'\bBoulevard\b': 'Blvd',
            r'\bRd\b': 'Rd',
            r'\bRoad\b': 'Rd',
            r'\bDr\b': 'Dr',
            r'\bDrive\b': 'Dr',
            r'\bLn\b': 'Ln',
            r'\bLane\b': 'Ln',
            r'\bCt\b': 'Ct',
            r'\bCourt\b': 'Ct',
            r'\bPl\b': 'Pl',
            r'\bPlace\b': 'Pl'
        }
        
        for pattern, replacement in replacements.items():
            address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)
        
        return address
    
    def _clean_visits(self, visits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and validate visits"""
        cleaned = []
        seen_stops = set()
        
        for visit in visits:
            # Skip duplicates
            if visit["stop_number"] in seen_stops:
                continue
            
            # Skip incomplete visits
            if not visit["address"] or len(visit["address"]) < 10:
                continue
            
            # Skip obviously invalid stops
            if visit["stop_number"] < 1 or visit["stop_number"] > 100:
                continue
            
            seen_stops.add(visit["stop_number"])
            cleaned.append(visit)
        
        # Sort by stop number
        cleaned.sort(key=lambda x: x["stop_number"])
        
        return cleaned
    
    def _extract_street_name(self, address: str) -> Optional[str]:
        """Extract street name from address"""
        # Common street name patterns
        street_patterns = [
            r'(\w+)\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place)',
            r'(\w+)\s+(?:North|South|East|West|N|S|E|W)\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard)',
        ]
        
        for pattern in street_patterns:
            match = re.search(pattern, address, re.IGNORECASE)
            if match:
                street_name = match.group(1).strip()
                # Filter out common non-street words
                if street_name.lower() not in ['the', 'at', 'of', 'and', 'on', 'in', 'to', 'for']:
                    return street_name.title()
        
        # For MyWay routes, try to extract first capitalized word as street name
        words = address.split()
        for word in words:
            if word[0].isupper() and len(word) > 2 and word.lower() not in ['the', 'at', 'of', 'and', 'on', 'in', 'to', 'for', 'colorado', 'springs', 'denver']:
                return word.title()
        
        # If no street name found, try to extract from the beginning of the address
        if address:
            first_word = address.split()[0] if address.split() else ""
            if first_word and first_word[0].isupper() and len(first_word) > 2:
                return first_word.title()
        
        return None
    
    def _find_healthcare_context(self, notes: List[str]) -> Optional[str]:
        """Find healthcare context in notes"""
        healthcare_keywords = {
            'hospital': 'Hospital',
            'medical': 'Medical Center',
            'health': 'Health Center',
            'care': 'Care Center',
            'clinic': 'Clinic',
            'rehab': 'Rehabilitation Center',
            'assisted': 'Assisted Living',
            'senior': 'Senior Living',
            'hospice': 'Hospice',
            'emergency': 'Emergency Room',
            'urgent': 'Urgent Care',
            'primary': 'Primary Care',
            'family': 'Family Medicine',
            'internal': 'Internal Medicine',
            'skilled': 'Skilled Nursing',
            'recovery': 'Recovery Center',
            'treatment': 'Treatment Center'
        }
        
        notes_text = ' '.join(notes).lower()
        for keyword, context in healthcare_keywords.items():
            if keyword in notes_text:
                return context
        
        return None

