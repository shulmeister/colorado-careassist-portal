import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
import re
import os
import tempfile
import time
from typing import Dict, Any, Optional, List, Tuple
import logging
import hashlib
from pytesseract import Output
import json
import httpx

logger = logging.getLogger(__name__)

# OpenAI API configuration for company name cleanup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Try to import numpy and OpenCV, but make them optional
try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # type: ignore
    logger.warning("NumPy not available, image preprocessing will be limited")

try:
    import cv2  # type: ignore
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV not available, will use PIL-based preprocessing only")

try:
    import easyocr  # type: ignore
    EASY_OCR_AVAILABLE = True
except ImportError:
    EASY_OCR_AVAILABLE = False
    easyocr = None  # type: ignore

try:
    from rapidocr_onnxruntime import RapidOCR  # type: ignore
    RAPID_OCR_AVAILABLE = True
except ImportError:
    RAPID_OCR_AVAILABLE = False
    RapidOCR = None  # type: ignore

class BusinessCardScanner:
    """Extract ONLY essential contact information: first name, last name, and email"""
    
    def __init__(self):
        # Focus ONLY on email pattern - this is the most reliable
        self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        self._easyocr_reader = None
        self._rapidocr_reader = None
        self._vowel_set = set("aeiouAEIOU")
        self._common_keywords = {
            "phone", "email", "manager", "care", "health", "medical", "center",
            "hospice", "clinic", "address", "cell", "mobile", "fax", "office",
            "contact", "colorado", "assist", "suite", "road", "street", "drive"
        }
    
    def scan_image(self, image_content: bytes) -> Dict[str, Any]:
        """Extract contact information from business card image"""
        try:
            # Debug: Log the content info
            logger.info(f"Image content length: {len(image_content)} bytes")
            logger.info(f"First 20 bytes: {image_content[:20]}")
            
            # Detect actual file format from magic bytes
            is_heic = image_content[:12] == b'\x00\x00\x004ftypheic' or image_content[:12] == b'\x00\x00\x00 ftyp'
            if is_heic:
                logger.warning("File appears to be HEIC format despite extension; attempting conversion")
            
            # Open image with explicit format handling
            image_buffer = io.BytesIO(image_content)
            
            # Try to open the image
            try:
                image = Image.open(image_buffer)
                image = ImageOps.exif_transpose(image)
                logger.info(f"Successfully opened image: {image.format}, mode: {image.mode}, size: {image.size}")
            except Exception as e:
                logger.error(f"Failed to open image with PIL: {str(e)}")
                # For HEIC files, register opener and try temp file approach
                try:
                    logger.info("Attempting HEIC via temporary file")
                    # Register HEIF opener
                    try:
                        from pillow_heif import register_heif_opener
                        register_heif_opener()
                        logger.info("Registered HEIF opener for HEIC files")
                    except ImportError as ie:
                        logger.error(f"Failed to import pillow_heif: {ie}")
                        raise ie
                    
                    image_buffer.seek(0)
                    
                    # Write bytes to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.heic') as temp_file:
                        temp_file.write(image_buffer.getvalue())
                        temp_file_path = temp_file.name
                    
                    try:
                        # Now PIL can open it with registered opener
                        image = Image.open(temp_file_path)
                        logger.info(f"Successfully opened HEIC via temp file: {image.mode}, size: {image.size}")
                    finally:
                        # Clean up temp file
                        os.unlink(temp_file_path)
                        
                except Exception as heif_error:
                    logger.error(f"Failed to open HEIC via temp file: {str(heif_error)}")
                    # Try pyheif as fallback
                    try:
                        logger.info("Attempting pyheif as fallback")
                        import pyheif
                        image_buffer.seek(0)
                        heif_file = pyheif.read_heif(image_buffer.getvalue())
                        # Convert to PIL Image
                        image = Image.frombytes(
                            heif_file.mode,
                            heif_file.size,
                            heif_file.data,
                            "raw",
                            heif_file.stride,
                            heif_file.orientation
                        )
                        logger.info(f"Successfully opened HEIC via pyheif: {image.mode}, size: {image.size}")
                    except Exception as pyheif_error:
                        logger.error(f"Failed to open HEIC via pyheif: {str(pyheif_error)}")
                        # Last resort: return friendly error message
                        logger.error("HEIC file could not be processed. Please try converting to JPEG/PNG first.")
                        raise Exception("Unable to process HEIC file. Please convert the image to JPEG or PNG format and try again.")
            
            # Convert to RGB if necessary (handles HEIC, RGBA, etc.)
            if image.mode not in ['RGB', 'L']:
                logger.info(f"Converting image from {image.mode} to RGB")
                image = image.convert('RGB')
            elif image.mode == 'L':
                # Convert single channel to RGB for consistent downstream handling
                image = image.convert('RGB')
            
            # Detect and crop to card bounds if possible
            image = self._crop_to_card_bounds(image)
            
            # Correct orientation and ensure minimum size for better OCR
            image = self._correct_orientation(image)
            image = self._ensure_minimum_size(image)
            
            # Try the lightweight rotation-based OCR used by the standalone tool first.
            text = ""
            simple_text = self._simple_rotational_ocr(image)
            if simple_text:
                simple_text = self._post_process_text(simple_text)
                simple_score = self._score_ocr_text(simple_text)
                has_email = bool(re.search(self.email_pattern, simple_text))
                if (has_email and simple_score >= 0.45) or simple_score >= 0.75:
                    logger.info(
                        "Simple rotational OCR succeeded (score %.3f, email=%s); skipping heavy pipeline",
                        simple_score,
                        has_email
                    )
                    text = simple_text
                else:
                    logger.info(
                        "Simple rotational OCR insufficient (score %.3f, email=%s); continuing with advanced pipeline",
                        simple_score,
                        has_email
                    )
            
            # Preprocess image for better OCR accuracy if simple pass didn't finish the job
            if not text:
                logger.info("Running advanced OCR pipeline...")
                logger.info(f"Normalized image size: {image.size}, mode: {image.mode}")
                
                processed_images = self._generate_processed_images(
                    image,
                    include_aggressive=False,
                    max_variants=4
                )
                text = self._extract_text_with_ocr(processed_images, image)
                logger.info(f"OCR extracted text length: {len(text)} characters")
                logger.info(f"First 500 chars of OCR text: {text[:500]}")
            
            # If OCR extracted very little text, try more aggressive preprocessing
            if len(text.strip()) < 120:
                logger.warning(
                    "OCR extracted limited text (%s chars). Attempting aggressive preprocessing.",
                    len(text)
                )
                aggressive_images = self._generate_processed_images(
                    image,
                    include_aggressive=True,
                    max_variants=2
                )
                text = self._extract_text_with_ocr(aggressive_images, image)
                logger.info("Aggressive preprocessing extracted %s characters", len(text))
                logger.info("Aggressive OCR sample: %s", text[:500])
            
            # Parse contact information
            contact_info = self._parse_contact_info(text)
            
            logger.info(f"Successfully scanned business card: {contact_info.get('name', 'Unknown')}")
            
            return {
                "success": True,
                "contact": contact_info,
                "raw_text": text
            }
            
        except Exception as e:
            logger.error(f"Error scanning business card: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to process image: {str(e)}",
                "contact": None
            }
    
    def _correct_orientation(self, image: Image.Image) -> Image.Image:
        """Use Tesseract OSD to auto-rotate the image if needed"""
        try:
            osd = pytesseract.image_to_osd(image, config='--psm 0')
            rotate_match = re.search(r'Rotate: (\d+)', osd)
            if rotate_match:
                angle = int(rotate_match.group(1))
                if angle and angle in {90, 180, 270}:
                    logger.info(f"Rotating image by {-angle} degrees based on OSD")
                    return image.rotate(-angle, expand=True)
        except Exception as e:
            logger.debug(f"Orientation detection failed: {str(e)}")
        return image
    
    def _ensure_minimum_size(
        self,
        image: Image.Image,
        min_dimension: int = 1200,
        max_dimension: int = 2000,
    ) -> Image.Image:
        """Resize image so it falls within the ideal OCR size range"""
        width, height = image.size
        smallest_side = min(width, height)
        largest_side = max(width, height)
        if smallest_side < min_dimension:
            scale_factor = min_dimension / smallest_side
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            logger.info(f"Upscaling image from {width}x{height} to {new_width}x{new_height}")
            return image.resize((new_width, new_height), Image.LANCZOS)
        if largest_side > max_dimension:
            scale_factor = max_dimension / largest_side
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            logger.info(f"Downscaling image from {width}x{height} to {new_width}x{new_height}")
            return image.resize((new_width, new_height), Image.LANCZOS)
        return image
    
    def _simple_rotational_ocr(self, image: Image.Image) -> str:
        """Lightweight OCR that tries a few rotations and contrast boosts."""
        try:
            base = image.convert('RGB')
            gray = base.convert('L')
            high_contrast = ImageEnhance.Contrast(gray).enhance(2.0)
            
            variants: List[Tuple[str, Image.Image]] = [
                ("original", gray),
                ("high_contrast", high_contrast),
                ("rotate_90", gray.rotate(90, expand=True)),
                ("rotate_180", gray.rotate(180, expand=True)),
                ("rotate_270", gray.rotate(270, expand=True)),
            ]
            
            best_text = ""
            best_score = -1
            phone_pattern = re.compile(r'\b\d{3}[\s\-.]?\d{3}[\s\-.]?\d{4}\b')
            
            for name, variant in variants:
                try:
                    text = pytesseract.image_to_string(variant, config="--oem 3 --psm 3", lang='eng')
                except Exception as exc:
                    logger.debug("Simple OCR variant %s failed: %s", name, exc)
                    continue
                
                if not text:
                    continue
                
                emails = re.findall(self.email_pattern, text)
                phones = phone_pattern.findall(text)
                score = len(emails) * 10 + len(phones) * 5 + len(text.split())
                
                logger.debug(
                    "Simple OCR variant %s produced %d chars, %d emails, %d phones (score %d)",
                    name,
                    len(text),
                    len(emails),
                    len(phones),
                    score
                )
                
                if score > best_score:
                    best_score = score
                    best_text = text
            
            return best_text
        except Exception as exc:
            logger.debug("Simple rotational OCR failed: %s", exc)
            return ""
    
    def _crop_to_card_bounds(self, image: Image.Image) -> Image.Image:
        """Use OpenCV to locate the main card area and crop tightly around it"""
        if not OPENCV_AVAILABLE:
            return image
        
        try:
            img_array = np.array(image.convert('RGB'))
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Invert if background is lighter
            white_ratio = np.mean(thresh == 255)
            if white_ratio < 0.5:
                thresh = cv2.bitwise_not(thresh)
            
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
            
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return image
            
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            image_area = img_array.shape[0] * img_array.shape[1]
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < image_area * 0.1:
                    continue
                
                rect = cv2.minAreaRect(contour)
                box = cv2.boxPoints(rect)
                box = np.int0(box)
                
                width = rect[1][0]
                height = rect[1][1]
                if width == 0 or height == 0:
                    continue
                
                # Deskew using perspective transform
                src_pts = box.astype("float32")
                
                # Order points
                s = src_pts.sum(axis=1)
                diff = np.diff(src_pts, axis=1)
                ordered = np.zeros((4, 2), dtype="float32")
                ordered[0] = src_pts[np.argmin(s)]
                ordered[2] = src_pts[np.argmax(s)]
                ordered[1] = src_pts[np.argmin(diff)]
                ordered[3] = src_pts[np.argmax(diff)]
                
                max_width = int(max(width, height))
                max_height = int(min(width, height))
                if max_width == 0 or max_height == 0:
                    continue
                
                dst_pts = np.array([
                    [0, 0],
                    [max_width - 1, 0],
                    [max_width - 1, max_height - 1],
                    [0, max_height - 1]
                ], dtype="float32")
                
                matrix = cv2.getPerspectiveTransform(ordered, dst_pts)
                warped = cv2.warpPerspective(img_array, matrix, (max_width, max_height))
                
                warped_image = Image.fromarray(warped)
                
                # Expand slightly to avoid cutting text near edges
                expanded = ImageOps.expand(warped_image, border=20, fill="white")
                logger.info("Cropped image to detected card bounds")
                return expanded
        except Exception as e:
            logger.debug(f"Failed to crop to card bounds: {str(e)}")
        
        return image
    
    def _generate_processed_images(
        self,
        image: Image.Image,
        include_aggressive: bool = True,
        max_variants: int = 8
    ) -> List[Image.Image]:
        """Create a set of processed image variants for OCR"""
        variants: List[Image.Image] = []
        
        base = image.copy()
        try:
            grayscale = base.convert('L')
            variants.append(grayscale)
            variants.append(ImageOps.autocontrast(grayscale))
            variants.append(ImageOps.equalize(grayscale))
        except Exception as e:
            logger.debug(f"Failed to convert to grayscale: {str(e)}")
        
        try:
            variants.append(self._preprocess_image(base.copy()))
        except Exception as e:
            logger.debug(f"Primary preprocessing failed: {str(e)}")
        
        pil_binarized = self._pil_binarize(base.copy())
        if pil_binarized is not None:
            variants.append(pil_binarized)
        
        opencv_binarized = self._opencv_binarize(base.copy()) if OPENCV_AVAILABLE else None
        if opencv_binarized is not None:
            variants.append(opencv_binarized)
        
        clahe_variant = self._apply_clahe(base.copy())
        if clahe_variant is not None:
            variants.append(clahe_variant)
        
        if include_aggressive:
            try:
                variants.append(self._aggressive_preprocess(base.copy()))
            except Exception as e:
                logger.debug(f"Aggressive preprocessing failed: {str(e)}")
        
        deduped = self._dedupe_images(variants)
        if max_variants and len(deduped) > max_variants:
            deduped = deduped[:max_variants]
        return deduped
    
    def _apply_clahe(self, image: Image.Image) -> Optional[Image.Image]:
        """Apply CLAHE-based contrast enhancement using OpenCV if available"""
        if not OPENCV_AVAILABLE or np is None or cv2 is None:
            return None
        
        try:
            rgb_array = np.array(image.convert('RGB'))
            lab_image = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab_image)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l_channel)
            merged = cv2.merge((cl, a_channel, b_channel))
            enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)
            enhanced_image = Image.fromarray(enhanced)
            return ImageOps.autocontrast(enhanced_image.convert('L'))
        except Exception as e:
            logger.debug(f"CLAHE preprocessing failed: {str(e)}")
            return None
    
    def _pil_binarize(self, image: Image.Image) -> Optional[Image.Image]:
        """Create a high-contrast binary version using PIL-only operations"""
        try:
            img = image.convert('L')
            img = ImageOps.autocontrast(img)
            img = img.filter(ImageFilter.MedianFilter(size=3))
            
            # Dynamic threshold based on median pixel intensity
            histogram = img.histogram()
            total_pixels = sum(histogram)
            cumulative = 0
            threshold = 180  # Fallback
            for intensity, count in enumerate(histogram):
                cumulative += count
                if cumulative >= total_pixels * 0.6:
                    threshold = intensity
                    break
            
            binary = img.point(lambda p: 255 if p > threshold else 0)
            return binary
        except Exception as e:
            logger.debug(f"PIL binarization failed: {str(e)}")
            return None
    
    def _opencv_binarize(self, image: Image.Image) -> Optional[Image.Image]:
        """Create a high-contrast binary version using OpenCV"""
        if not OPENCV_AVAILABLE:
            return None
        
        try:
            img_array = np.array(image.convert('RGB'))
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            gray = cv2.bilateralFilter(gray, 9, 75, 75)
            thresh = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                2
            )
            return Image.fromarray(thresh)
        except Exception as e:
            logger.debug(f"OpenCV binarization failed: {str(e)}")
            return None
    
    def _dedupe_images(self, images: List[Image.Image]) -> List[Image.Image]:
        """Remove duplicate image variants based on hash"""
        unique_images: List[Image.Image] = []
        seen_hashes = set()
        
        for img in images:
            if img is None:
                continue
            try:
                fingerprint = hashlib.md5(img.tobytes()).hexdigest()
            except Exception:
                # Fallback to object id if tobytes fails (e.g., mode 1 images)
                fingerprint = str(id(img))
            if fingerprint not in seen_hashes:
                seen_hashes.add(fingerprint)
                unique_images.append(img)
        
        return unique_images
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image to improve OCR accuracy"""
        # Resize image if too small (Tesseract works better with larger images)
        width, height = image.size
        min_dimension = 300
        if width < min_dimension or height < min_dimension:
            scale_factor = max(min_dimension / width, min_dimension / height)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            image = image.resize((new_width, new_height), Image.LANCZOS)
            logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")
        
        if OPENCV_AVAILABLE:
            try:
                # Convert PIL Image to numpy array for OpenCV processing
                img_array = np.array(image)
                
                # Convert RGB to BGR for OpenCV
                if len(img_array.shape) == 3:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # Convert to grayscale
                gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY) if len(img_array.shape) == 3 else img_array
                
                # Apply denoising
                denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
                
                # Apply Gaussian blur to reduce noise
                blurred = cv2.GaussianBlur(denoised, (3, 3), 0)
                
                # Apply adaptive thresholding for better contrast
                thresh = cv2.adaptiveThreshold(
                    blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                )
                
                # Apply morphological operations to clean up the image
                kernel = np.ones((1, 1), np.uint8)
                cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
                
                # Convert back to PIL Image
                processed = Image.fromarray(cleaned)
                
                logger.info("Image preprocessing completed with OpenCV")
                return processed
                
            except Exception as e:
                logger.warning(f"OpenCV preprocessing failed: {str(e)}, falling back to PIL")
        
        # Fallback: use PIL-based preprocessing
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast (more aggressive)
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.5)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.5)
            
            # Apply unsharp mask for better text clarity
            image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            
            logger.info("Image preprocessing completed with PIL")
            return image
        except Exception as e2:
            logger.warning(f"PIL preprocessing also failed: {str(e2)}, using original")
            return image
    
    def _aggressive_preprocess(self, image: Image.Image) -> Image.Image:
        """More aggressive preprocessing for difficult images"""
        try:
            # Make a copy
            img = image.copy()
            
            # Resize to larger size for better OCR
            width, height = img.size
            scale_factor = max(600 / width, 600 / height) if max(width, height) < 600 else 1.5
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Convert to grayscale
            if img.mode != 'L':
                img = img.convert('L')
            
            # Extreme contrast enhancement
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(3.0)
            
            # Extreme sharpness
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(3.0)
            
            # Brightness adjustment
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.2)
            
            # Unsharp mask
            img = img.filter(ImageFilter.UnsharpMask(radius=3, percent=200, threshold=2))
            
            logger.info("Aggressive preprocessing completed")
            return img
        except Exception as e:
            logger.warning(f"Aggressive preprocessing failed: {str(e)}")
            return image
    
    def _get_easyocr_reader(self):
        """Lazily initialize and return the EasyOCR reader if available"""
        if not EASY_OCR_AVAILABLE:
            return None
        if self._easyocr_reader is not None:
            return self._easyocr_reader
        try:
            self._easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            logger.info("EasyOCR reader initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize EasyOCR reader: %s", exc)
            self._easyocr_reader = None
        return self._easyocr_reader
    
    def _easyocr_fallback(self, image: Image.Image) -> str:
        """Fallback OCR using EasyOCR when Tesseract output scores poorly"""
        reader = self._get_easyocr_reader()
        if reader is None or np is None:
            return ""
        
        try:
            ocr_results = reader.readtext(np.array(image.convert('RGB')), detail=0, paragraph=True)
            cleaned = self._clean_ocr_text('\n'.join(result for result in ocr_results if isinstance(result, str)))
            if cleaned:
                logger.info("EasyOCR fallback produced %d characters", len(cleaned))
            return cleaned
        except Exception as exc:
            logger.warning("EasyOCR fallback failed: %s", exc)
            return ""

    def _get_rapidocr_reader(self):
        """Lazily initialize the RapidOCR reader when available"""
        if not RAPID_OCR_AVAILABLE:
            return None
        if self._rapidocr_reader is not None:
            return self._rapidocr_reader
        if np is None:
            return None
        try:
            self._rapidocr_reader = RapidOCR()
            logger.info("RapidOCR reader initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize RapidOCR reader: %s", exc)
            self._rapidocr_reader = None
        return self._rapidocr_reader

    def _rapidocr_fallback(self, image: Image.Image) -> str:
        """Fallback OCR using RapidOCR (ONNX) when Tesseract/EasyOCR output is weak"""
        reader = self._get_rapidocr_reader()
        if reader is None or np is None:
            return ""
        try:
            result, _ = reader(np.array(image.convert('RGB')))
        except Exception as exc:
            logger.warning("RapidOCR fallback failed: %s", exc)
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
            cleaned = self._clean_ocr_text(text)
            if cleaned:
                lines.append(cleaned)
        combined = '\n'.join(lines)
        return self._post_process_text(combined)
    
    def _extract_text_with_ocr(self, processed_images: List[Image.Image], original_image: Image.Image) -> str:
        """Extract text quickly while staying within Heroku's 30s request limit"""
        if processed_images is None:
            processed_images = []
        
        start_time = time.perf_counter()
        try:
            max_time_budget = float(os.environ.get("OCR_TIME_BUDGET_SECONDS", "24"))
        except ValueError:
            max_time_budget = 24.0
        
        def within_budget() -> bool:
            return (time.perf_counter() - start_time) < max_time_budget
        
        ocr_results: List[Dict[str, Any]] = []
        seen_texts: set[str] = set()
        best_entry: Optional[Dict[str, Any]] = None
        rapid_primary_text: Optional[str] = None
        rapid_primary_score: float = 0.0
        
        def register_text(
            text: str,
            source: str,
            variant: Optional[int],
            base_score: Optional[float] = None
        ) -> bool:
            """Store candidate OCR text and return True if we can stop early"""
            nonlocal best_entry
            if not text:
                return False
            cleaned = self._clean_ocr_text(text)
            processed = self._post_process_text(cleaned) or cleaned
            if not processed or processed in seen_texts:
                return False
            score = base_score if base_score is not None else self._score_ocr_text(processed)
            if score < 0.2:
                return False
            entry = {
                "score": score,
                "text": processed,
                "source": source,
                "variant": variant
            }
            ocr_results.append(entry)
            seen_texts.add(processed)
            if (
                best_entry is None
                or score > best_entry["score"]
                or (score == best_entry["score"] and len(processed) > len(best_entry["text"]))
            ):
                best_entry = entry
            has_email = bool(re.search(self.email_pattern, processed))
            return score >= 0.9 and has_email
        
        # RapidOCR first – fast and accurate, skips heavier Tesseract passes if good enough
        if RAPID_OCR_AVAILABLE and within_budget():
            rapid_text = self._rapidocr_fallback(original_image)
            if rapid_text:
                rapid_primary_text = rapid_text
                rapid_primary_score = self._score_ocr_text(rapid_text)
                if rapid_primary_score >= 0.55 and re.search(self.email_pattern, rapid_text):
                    logger.info("RapidOCR produced high-confidence result; skipping Tesseract")
                    return rapid_text
                register_text(rapid_text, "rapidocr", -1, base_score=rapid_primary_score)
                rapid_primary_text = self._post_process_text(rapid_text) or rapid_text
                rapid_primary_score = self._score_ocr_text(rapid_primary_text)
        
        # Build a lean set of variants to keep memory and runtime low
        images_to_try: List[Image.Image] = [img for img in processed_images if img is not None]
        images_to_try.append(original_image)
        
        inverted_variants: List[Image.Image] = []
        for base_img in images_to_try[:2]:
            if base_img is None:
                continue
            try:
                inverted = ImageOps.invert(base_img.convert('L')).convert('RGB')
                inverted_variants.append(inverted)
            except Exception as invert_error:
                logger.debug("Variant inversion failed: %s", invert_error)
        images_to_try.extend(inverted_variants)
        
        images_to_try = self._dedupe_images(images_to_try)
        max_variants_to_try = 5
        if len(images_to_try) > max_variants_to_try:
            images_to_try = images_to_try[:max_variants_to_try]
        
        primary_configs = [
            ("psm6_whitelist", '--oem 3 --psm 6 --dpi 300 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@._-()/: '),
            ("psm6", '--oem 3 --psm 6 --dpi 300 -c preserve_interword_spaces=1'),
        ]
        secondary_configs = [
            ("psm11", '--oem 3 --psm 11 --dpi 300'),
        ]
        
        stop_requested = False
        for image_index, img in enumerate(images_to_try):
            if stop_requested or not within_budget():
                break
            if img is None:
                continue
            for config_name, config in primary_configs:
                if stop_requested or not within_budget():
                    break
                try:
                    raw_text = pytesseract.image_to_string(img, config=config, lang='eng')
                except Exception as exc:
                    logger.warning("OCR (%s) failed on variant %d: %s", config_name, image_index, exc)
                    continue
                
                logger.info(
                    "OCR (%s, variant %d) produced %d characters",
                    config_name,
                    image_index,
                    len(raw_text.strip())
                )
                
                if register_text(raw_text, f"{config_name}_string", image_index):
                    stop_requested = True
                    break
                
                if within_budget() and (best_entry is None or best_entry["score"] < 0.9):
                    try:
                        data_text, avg_conf = self._extract_text_from_data(img, config)
                    except Exception as data_exc:
                        logger.debug("image_to_data failed (%s variant %d): %s", config_name, image_index, data_exc)
                        data_text, avg_conf = "", 0.0
                    if data_text:
                        combined_score = max(self._score_ocr_text(data_text), (avg_conf / 100.0) + 0.1)
                        if register_text(data_text, f"{config_name}_data", image_index, base_score=combined_score):
                            stop_requested = True
                            break
        
        # Secondary configs for stubborn cards, but only if we still have time and no strong hit
        if not stop_requested and within_budget() and (best_entry is None or best_entry["score"] < 0.6):
            for image_index, img in enumerate(images_to_try[:2]):
                if stop_requested or not within_budget():
                    break
                if img is None:
                    continue
                for config_name, config in secondary_configs:
                    if stop_requested or not within_budget():
                        break
                    try:
                        raw_text = pytesseract.image_to_string(img, config=config, lang='eng')
                    except Exception as exc:
                        logger.debug("Secondary OCR (%s) failed on variant %d: %s", config_name, image_index, exc)
                        continue
                    if register_text(raw_text, f"{config_name}_string", image_index):
                        stop_requested = True
                        break
        
        if not ocr_results:
            logger.warning("OCR pipeline produced no usable text; trying lightweight fallbacks")
            if within_budget():
                easy_text = self._easyocr_fallback(original_image)
                if easy_text:
                    easy_text = self._post_process_text(easy_text) or easy_text
                    if easy_text:
                        return easy_text
            if RAPID_OCR_AVAILABLE:
                rapid_text = self._rapidocr_fallback(original_image)
                if rapid_text:
                    return rapid_text
            try:
                fallback_text = pytesseract.image_to_string(original_image, config='--oem 3 --psm 6 --dpi 280', lang='eng')
                cleaned = self._clean_ocr_text(fallback_text)
                return self._post_process_text(cleaned)
            except Exception as exc:
                logger.error("Fallback OCR failed: %s", exc)
                return ""
        
        ocr_results.sort(key=lambda item: (item["score"], len(item["text"])), reverse=True)
        best_text = ocr_results[0]["text"]
        best_score = ocr_results[0]["score"]
        
        for candidate in ocr_results[1:]:
            if candidate["score"] < max(best_score - 0.18, 0.25):
                continue
            best_text = self._merge_text(best_text, candidate["text"])
        
        if not re.search(self.email_pattern, best_text):
            for candidate in ocr_results:
                if re.search(self.email_pattern, candidate["text"]):
                    best_text = self._merge_text(best_text, candidate["text"])
                    break
        
        best_text = self._post_process_text(best_text)
        if within_budget() and best_score < 0.5:
            easy_text = self._easyocr_fallback(original_image)
            if easy_text:
                easy_text = self._post_process_text(easy_text) or easy_text
                if easy_text:
                    easy_score = self._score_ocr_text(easy_text)
                    if easy_score > best_score:
                        logger.info(
                            "EasyOCR fallback improved score from %.3f to %.3f",
                            best_score,
                            easy_score
                        )
                        best_text = easy_text
                        best_score = easy_score
                    elif easy_score >= max(best_score - 0.1, 0.25):
                        merged = self._merge_text(best_text, easy_text)
                        best_text = self._post_process_text(merged) or merged
                        best_score = self._score_ocr_text(best_text)
        
        if RAPID_OCR_AVAILABLE and within_budget() and best_score < 0.5:
            rapid_text = self._rapidocr_fallback(original_image)
            if rapid_text:
                rapid_score = self._score_ocr_text(rapid_text)
                if rapid_score > best_score:
                    logger.info(
                        "RapidOCR fallback improved score from %.3f to %.3f",
                        best_score,
                        rapid_score
                    )
                    best_text = rapid_text
                    best_score = rapid_score
                elif rapid_score >= max(best_score - 0.12, 0.3):
                    merged = self._merge_text(best_text, rapid_text)
                    best_text = self._post_process_text(merged) or merged
                    best_score = self._score_ocr_text(best_text)
        
        if rapid_primary_text:
            rapid_primary_text = self._post_process_text(rapid_primary_text) or rapid_primary_text
            rapid_primary_score = self._score_ocr_text(rapid_primary_text)
            if (
                (best_score < 0.55 and rapid_primary_score >= 0.45)
                or (self._text_is_gibberish(best_text) and rapid_primary_score >= best_score * 0.8)
            ):
                logger.info(
                    "RapidOCR text selected over Tesseract output (scores rapid=%.3f, tess=%.3f)",
                    rapid_primary_score,
                    best_score
                )
                best_text = rapid_primary_text
        
        return best_text
    
    def _clean_ocr_text(self, text: str) -> str:
        """Clean and normalize OCR text"""
        if not text:
            return ""
        
        if isinstance(text, list):
            text = "\n".join(text)
        
        # Remove excessive whitespace
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line:
                # Normalize spaces
                line = ' '.join(line.split())
                lines.append(line)
        
        # Join lines back
        cleaned = '\n'.join(lines)
        
        return cleaned

    def _score_ocr_text(self, text: str) -> float:
        """Score OCR text based on character quality and presence of key patterns"""
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
        
        base_score = (letters + 0.6 * digits + 0.3 * punctuation) / length
        
        words = [word for word in re.findall(r"[A-Za-z]+", stripped) if len(word) > 1]
        if words:
            vowel_words = sum(1 for word in words if any(ch in self._vowel_set for ch in word))
            vowel_ratio = vowel_words / max(len(words), 1)
            if vowel_ratio < 0.35:
                base_score *= 0.35
            else:
                base_score *= 1.05
            
            avg_word_length = sum(len(word) for word in words) / len(words)
            if avg_word_length < 2.2:
                base_score *= 0.4
            elif avg_word_length > 9:
                base_score *= 0.7
            
            keyword_hits = sum(1 for word in words if word.lower() in self._common_keywords)
            if keyword_hits:
                base_score += min(keyword_hits, 4) * 0.08
        else:
            base_score *= 0.2
        
        if '@' in stripped:
            base_score += 0.4
        if any(keyword in stripped.lower() for keyword in ['email', 'phone', 'manager', 'center', 'case', 'nursing', 'care']):
            base_score += 0.2
        
        unique_chars = len(set(stripped))
        if unique_chars <= length * 0.2:
            base_score *= 0.5
        
        word_count = len(stripped.split())
        if word_count >= 4:
            base_score += 0.1
        
        return min(base_score, 2.2)

    def _line_is_valid(self, line: str) -> bool:
        """Heuristic to determine if an OCR line looks meaningful"""
        if not line or len(line) < 3:
            return False
        
        letters = sum(1 for ch in line if ch.isalpha())
        length = len(line)
        
        if letters < 2:
            return False
        
        ratio = letters / max(length, 1)
        if ratio < 0.4:
            return False
        
        vowel_ratio = sum(1 for ch in line if ch in self._vowel_set) / max(length, 1)
        if vowel_ratio < 0.25:
            return False
        
        return self._score_ocr_text(line) >= 0.2
    
    def _merge_text(self, base_text: str, new_text: str) -> str:
        """Merge OCR outputs while avoiding duplicate or noisy lines"""
        if not new_text:
            return base_text
        
        base_lines = [line.strip() for line in base_text.split('\n') if line.strip()]
        seen_lines = set(base_lines)
        
        for line in new_text.split('\n'):
            line = line.strip()
            if not line or line in seen_lines:
                continue
            if not self._line_is_valid(line):
                continue
            base_lines.append(line)
            seen_lines.add(line)
        
        return '\n'.join(base_lines)

    def _post_process_text(self, text: str) -> str:
        """Remove obviously garbled lines while preserving key contact details"""
        if not text:
            return ""
        filtered_lines: List[str] = []
        fallback_lines: List[str] = []
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            fallback_lines.append(stripped)
            if (
                self._line_is_valid(stripped)
                or re.search(self.email_pattern, stripped)
                or self._looks_like_name(stripped)
                or self._extract_phone(stripped)
            ):
                filtered_lines.append(stripped)
        if filtered_lines:
            return '\n'.join(filtered_lines)
        return '\n'.join(fallback_lines)

    def _text_is_gibberish(self, text: str) -> bool:
        if not text:
            return True
        score = self._score_ocr_text(text)
        if score >= 0.35:
            return False
        letters = ''.join(ch for ch in text if ch.isalpha())
        if not letters:
            return True
        vowel_ratio = sum(ch in self._vowel_set for ch in letters) / max(len(letters), 1)
        return vowel_ratio < 0.2 and '@' not in text

    def _extract_text_from_data(self, image: Image.Image, config: str) -> Tuple[str, float]:
        """Use pytesseract image_to_data to build text from high-confidence words"""
        try:
            ocr_data = pytesseract.image_to_data(
                image,
                config=config,
                lang='eng',
                output_type=Output.DICT
            )
        except Exception as e:
            logger.debug(f"image_to_data failed: {str(e)}")
            return "", 0.0
        
        line_map: Dict[Tuple[int, int, int], List[str]] = {}
        line_conf_map: Dict[Tuple[int, int, int], List[float]] = {}
        confidences = ocr_data.get("conf", [])
        texts = ocr_data.get("text", [])
        block_nums = ocr_data.get("block_num", [])
        par_nums = ocr_data.get("par_num", [])
        line_nums = ocr_data.get("line_num", [])
        
        for idx, word in enumerate(texts):
            try:
                conf = float(confidences[idx])
            except (ValueError, TypeError):
                conf = -1.0
            
            word_clean = word.strip()
            if not word_clean:
                continue
            if conf < 55:
                continue
            
            key = (
                block_nums[idx] if idx < len(block_nums) else 0,
                par_nums[idx] if idx < len(par_nums) else 0,
                line_nums[idx] if idx < len(line_nums) else idx
            )
            line_map.setdefault(key, []).append(word_clean)
            line_conf_map.setdefault(key, []).append(conf)
        
        if not line_map:
            return "", 0.0
        
        # Sort keys to maintain reading order
        sorted_lines = sorted(line_map.items(), key=lambda item: item[0])
        reconstructed_lines: List[str] = []
        confidences_used: List[float] = []
        
        for key, words in sorted_lines:
            if not words:
                continue
            line_text = self._clean_ocr_text(' '.join(words))
            if not line_text:
                continue
            conf_values = line_conf_map.get(key, [])
            avg_conf = sum(conf_values) / max(len(conf_values), 1) if conf_values else 0.0
            if not self._line_is_valid(line_text) and avg_conf < 70:
                continue
            reconstructed_lines.append(line_text)
            confidences_used.append(avg_conf)
        
        if not reconstructed_lines:
            return "", 0.0
        
        average_confidence = sum(confidences_used) / max(len(confidences_used), 1)
        return '\n'.join(reconstructed_lines), average_confidence
    
    def _parse_contact_info(self, text: str) -> Dict[str, Any]:
        """Parse ONLY essential contact information: first name, last name, and email"""
        contact = {
            "first_name": None,
            "last_name": None,
            "email": None,
            "name": None,  # For backward compatibility
            "company": None,  # Will be derived from email domain
            "title": None,
            "phone": None,
            "website": None,
            "address": None,
            "notes": text.strip()
        }
        
        # STEP 1: Extract email (most reliable)
        email_match = re.search(self.email_pattern, text)
        if email_match:
            contact['email'] = email_match.group().lower().strip()
            
            # Extract company from email domain
            email_parts = contact['email'].split('@')
            if len(email_parts) == 2:
                domain = email_parts[1].split('.')[0]  # Get domain without .com, .org, etc.
                # Clean up common domain patterns
                domain = domain.replace('-', ' ').replace('_', ' ')
                contact['company'] = domain.title()
        
        # STEP 2: Extract name using multiple strategies
        name = self._extract_name(text)
        if name:
            contact['name'] = name
            # Try to split into first and last name
            name_parts = name.split()
            if len(name_parts) >= 2:
                contact['first_name'] = name_parts[0].strip()
                contact['last_name'] = ' '.join(name_parts[1:]).strip()
            else:
                contact['first_name'] = name.strip()
        
        # STEP 3: Extract company from text if no email-derived company
        if not contact['company']:
            contact['company'] = self._extract_company(text)
        
        # STEP 3.5: Clean up company name using AI if available
        if contact['company']:
            contact['company'] = self._cleanup_company_name_with_ai(contact['company'])
        
        # STEP 4: Extract phone number
        contact['phone'] = self._extract_phone(text)
        
        # STEP 5: Extract website
        contact['website'] = self._extract_website(text)
        
        # STEP 6: Extract title
        contact['title'] = self._extract_title(text)
        
        return contact
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract the most likely name from OCR text"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Strategy 1: First line that looks like a name (may include credentials like MSN, RN)
        for line in lines[:5]:  # Check first 5 lines
            # Remove common credentials and titles
            cleaned_line = self._clean_name_line(line)
            if cleaned_line and self._looks_like_name(cleaned_line):
                return cleaned_line
        
        # Strategy 2: Look for email and extract name from it
        email_match = re.search(self.email_pattern, text)
        if email_match:
            email = email_match.group()
            # Extract name from email (e.g., Kirsten.Burton@gentivahs.com -> Kirsten Burton)
            email_parts = email.split('@')[0]
            if '.' in email_parts:
                name_parts = email_parts.split('.')
                if len(name_parts) == 2:
                    potential_name = f"{name_parts[0].title()} {name_parts[1].title()}"
                    # Verify it looks like a name
                    if self._looks_like_name(potential_name):
                        return potential_name
        
        # Strategy 3: Look for capitalized words that aren't email addresses
        words = text.split()
        name_candidates = []
        
        for word in words:
            # Skip if it's an email, phone number, or common business words
            if (re.search(self.email_pattern, word) or 
                re.search(r'\d{3,}', word) or  # Phone numbers
                word.lower() in ['inc', 'llc', 'corp', 'company', 'hospital', 'medical', 'health', 'center', 'clinic', 'the', 'and', 'of', 'for', 'hospice']):
                continue
            
            # Skip credentials
            if word.upper() in ['MSN', 'RN', 'MD', 'DO', 'PA', 'NP', 'LPN', 'BSN', 'MBA', 'PhD']:
                continue
            
            # If it's capitalized and looks like a name part
            if word[0].isupper() and len(word) > 1 and word.replace('.', '').replace('-', '').isalpha():
                name_candidates.append(word)
        
        # If we found 2-4 name-like words, combine them
        if 2 <= len(name_candidates) <= 4:
            return ' '.join(name_candidates)
        
        return None
    
    def _clean_name_line(self, line: str) -> str:
        """Remove credentials and titles from a name line"""
        # Remove common credentials (MSN, RN, MD, etc.)
        credentials = ['MSN', 'RN', 'MD', 'DO', 'PA', 'NP', 'LPN', 'BSN', 'MBA', 'PhD', 'DNP']
        cleaned = line
        for cred in credentials:
            # Remove credential with commas around it
            cleaned = re.sub(r',\s*' + re.escape(cred) + r'(?:\s|,|$)', '', cleaned, flags=re.IGNORECASE)
            # Remove credential at end
            cleaned = re.sub(r'\s+' + re.escape(cred) + r'$', '', cleaned, flags=re.IGNORECASE)
        
        # Remove common titles
        titles = ['Patient Care Manager', 'Manager', 'Director', 'Coordinator', 'Specialist', 'Assistant']
        for title in titles:
            cleaned = re.sub(r',\s*' + re.escape(title) + r'(?:\s|,|$)', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+' + re.escape(title) + r'$', '', cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()
    
    def _looks_like_name(self, text: str) -> bool:
        """Check if text looks like a person's name"""
        # Skip if it's an email
        if re.search(self.email_pattern, text):
            return False
        
        # Skip if it contains numbers (likely phone or address)
        if re.search(r'\d', text):
            return False
        
        # Skip if it's too long (likely company name or address)
        if len(text) > 30:
            return False
        
        # Skip if it's all caps (likely company name)
        if text.isupper():
            return False
        
        # Skip common business words
        business_words = ['inc', 'llc', 'corp', 'company', 'hospital', 'medical', 'health', 'center', 'clinic', 'manager', 'director', 'coordinator']
        if any(word in text.lower() for word in business_words):
            return False
        
        # Must have at least 2 words and start with capital letter
        words = text.split()
        if len(words) < 2:
            return False
        
        # All words should start with capital letters
        if not all(word[0].isupper() for word in words if word):
            return False
        
        return True
    
    def _extract_company(self, text: str) -> Optional[str]:
        """Extract company name from OCR text"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Look for company name patterns in first few lines
        for line in lines[:5]:
            # Skip if it looks like a person's name
            if self._looks_like_name(line):
                continue
            
            # Skip if it contains common non-company patterns
            if any(word in line.lower() for word in ['ph:', 'fax:', 'your', 'source', 'medical providers']):
                continue
            
            # Skip if it's an address pattern
            if re.search(r'\d+.*(st|ave|rd|blvd|street|avenue)', line.lower()):
                continue
            
            # Skip if it's a phone number
            if re.search(r'\d{3}-\d{3}-\d{4}', line):
                continue
            
            # Skip if it's a website URL (but keep company names that might have .com)
            if line.startswith('http') or line.startswith('www.'):
                continue
            
            # Skip if it's a title
            title_keywords = ['manager', 'director', 'coordinator', 'specialist', 'assistant']
            if any(keyword in line.lower() for keyword in title_keywords) and len(line) < 30:
                continue
            
            # If line looks like a company name, return it
            # Company names are usually 3-50 characters
            if len(line) > 3 and len(line) < 50:
                # Prefer lines that are not all caps (but allow some caps)
                if not line.isupper() or len(line.split()) <= 3:
                    return line.strip()
        
        return None
    
    def _cleanup_company_name_with_ai(self, raw_company: str) -> str:
        """Use OpenAI to clean up OCR errors in company names"""
        if not raw_company or not OPENAI_API_KEY:
            return raw_company
        
        try:
            # Use OpenAI to fix OCR errors
            response = httpx.post(
                OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an OCR text correction assistant. Fix OCR errors in company names. Common issues: missing spaces between words (e.g. 'Cokidneycare' → 'CO Kidney Care'), missing letters (e.g. 'Sunri e Living' → 'Sunrise Living'), extra spaces within words (e.g. 'En ign ervice' → 'Ensign Services'). Return ONLY the corrected company name, nothing else."
                        },
                        {
                            "role": "user",
                            "content": f"Fix this company name: {raw_company}"
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 50
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                cleaned = result['choices'][0]['message']['content'].strip()
                # Remove quotes if present
                cleaned = cleaned.strip('"\'')
                logger.info(f"AI cleaned company name: '{raw_company}' → '{cleaned}'")
                return cleaned
            else:
                logger.warning(f"OpenAI API error: {response.status_code}")
                return raw_company
                
        except Exception as e:
            logger.warning(f"Failed to clean company name with AI: {e}")
            return raw_company
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number from text"""
        # Common phone patterns
        phone_patterns = [
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (719) 330-6652 or 719-330-6652
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',  # 719 330 6652
            r'O\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # O (719) 330-6652
            r'Office[:\s]+\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # Office: (719) 330-6652
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phone = match.group()
                # Clean up the phone number
                phone = re.sub(r'[Oo]ffice[:\s]+', '', phone, flags=re.IGNORECASE)
                phone = re.sub(r'^[Oo]\s+', '', phone)
                return phone.strip()
        
        return None
    
    def _extract_website(self, text: str) -> Optional[str]:
        """Extract website URL from text"""
        # Look for website patterns
        website_patterns = [
            r'https?://[\w\.-]+',  # http://example.com
            r'www\.[\w\.-]+',  # www.example.com
            r'[\w\.-]+\.(com|org|net|edu|gov|io|co)[\w\.-]*',  # example.com
        ]
        
        for pattern in website_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                website = match.group()
                # Clean up
                website = website.strip()
                # Add http:// if missing
                if not website.startswith('http'):
                    website = 'https://' + website.lstrip('www.')
                return website
        
        return None
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Extract job title from text"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Common titles to look for
        title_keywords = [
            'Patient Care Manager', 'Manager', 'Director', 'Coordinator', 
            'Specialist', 'Assistant', 'Executive', 'President', 'VP',
            'Vice President', 'Chief', 'Lead', 'Supervisor'
        ]
        
        for line in lines[:8]:  # Check first 8 lines
            line_lower = line.lower()
            # Skip if it's a name
            if self._looks_like_name(line):
                continue
            # Skip if it's an email or phone
            if re.search(self.email_pattern, line) or re.search(r'\d{3}', line):
                continue
            
            # Check if line contains title keywords
            for keyword in title_keywords:
                if keyword.lower() in line_lower:
                    return line.strip()
            
            # If line is short and doesn't look like company/address, might be title
            if 5 < len(line) < 40 and not re.search(r'\d', line):
                # Check if it's not a company name (all caps or very long)
                if not line.isupper() and not any(word in line_lower for word in ['inc', 'llc', 'corp', 'company']):
                    return line.strip()
        
        return None
    
    def validate_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean ONLY essential contact information"""
        validated = contact.copy()
        
        # Clean email (most important)
        if validated.get('email'):
            validated['email'] = validated['email'].lower().strip()
        
        # Clean names
        if validated.get('first_name'):
            validated['first_name'] = validated['first_name'].strip().title()
        
        if validated.get('last_name'):
            validated['last_name'] = validated['last_name'].strip().title()
        
        if validated.get('name'):
            validated['name'] = validated['name'].strip().title()
        
        # Clean company (derived from email domain)
        if validated.get('company'):
            validated['company'] = validated['company'].strip()
        
        # Set empty fields to None for cleaner Mailchimp export
        for field in ['title', 'phone', 'website', 'address']:
            if not validated.get(field):
                validated[field] = None
        
        return validated
