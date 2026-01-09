#!/usr/bin/env python3
"""Import existing leads from Google Sheet data"""
from app import app, db, Lead, User
import re

def clean_phone(phone):
    """Clean phone number format"""
    if not phone:
        return None
    
    # Remove common prefixes and clean up
    phone = str(phone).strip()
    phone = phone.replace('p:', '').replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
    
    # Add +1 if it doesn't start with +
    if phone and not phone.startswith('+'):
        if len(phone) == 10:
            phone = '+1' + phone
        elif len(phone) == 11 and phone.startswith('1'):
            phone = '+' + phone
    
    return phone if phone else None

def extract_sentiment(notes):
    """Extract sentiment from notes"""
    if not notes:
        return 'neutral'
    
    notes_lower = notes.lower()
    
    # Positive indicators
    positive_words = ['hired', 'interested', 'application', 'experience', 'available', 'cna', 'exp']
    # Negative indicators  
    negative_words = ['not interested', 'quit', 'wrong', 'unavailable', 'no response', 'disconnected']
    
    positive_count = sum(1 for word in positive_words if word in notes_lower)
    negative_count = sum(1 for word in negative_words if word in notes_lower)
    
    if negative_count > positive_count:
        return 'negative'
    elif positive_count > negative_count:
        return 'positive'
    else:
        return 'neutral'

def determine_status_from_notes(notes):
    """Determine lead status based on notes content."""
    if not notes or notes.strip() == '':
        return 'new'
    
    # If there are notes, they were contacted
    return 'contacted'

# Complete data from your CSV file (reversed order - newest first)
leads_data = [
    {"name": "Brian Santistevan", "email": "tk741000@gmail.com", "phone": "+17194061267", "notes": ""},
    {"name": "Crystal Gonzales", "email": "crystalpatience24@gmail.com", "phone": "+17193556444", "notes": ""},
    {"name": "Eva Vedia", "email": "eva.vedia@icloud.com", "phone": "+17199313696", "notes": ""},
    {"name": "Katherine Warner", "email": "kathyawarner2@gmail.com", "phone": "+17204686761", "notes": ""},
    {"name": "Steifi Otup", "email": "Otupsteifi9@gmail.com", "phone": "+17122546398", "notes": ""},
    {"name": "Daniel Damien Peralta", "email": "peraltadaniel2@gmail.com", "phone": "+19705087344", "notes": ""},
    {"name": "Maura Morris", "email": "maurafay1927@gmail.com", "phone": "+15122298479", "notes": ""},
    {"name": "Chris Marez", "email": "czeram83@gmail.com", "phone": "+17194044066", "notes": ""},
    {"name": "Les Dorn", "email": "leslie_dorn@comcast.net", "phone": "+13039124999", "notes": ""},
    {"name": "Georgina Garcia", "email": "georgina48g@gmail.com", "phone": "+17193078621", "notes": ""},
    {"name": "Tonya Gonzales", "email": "tonyagonzales3131@gmail.com", "phone": "+17206765012", "notes": ""},
    {"name": "Kelly Trevino", "email": "kellytrevino044@gmail.com", "phone": "+19702315168", "notes": ""},
    {"name": "Kimberly Bashaw", "email": "kimberlybashaw@gmail.com", "phone": "+16304083026", "notes": ""},
    {"name": "Kristopher Dee Koetting", "email": "kriskoetting@gmail.com", "phone": "+18083154346", "notes": ""},
    {"name": "Leslie Mercado Gomez", "email": "gomezleslie717@gmail.com", "phone": "+15628891966", "notes": ""},
    {"name": "J Bowers", "email": "Bowersjeannette90@gmail.com", "phone": "+17738613475", "notes": ""},
    {"name": "Lisa Jo", "email": "happylooker@yahoo.com", "phone": "+17194938284", "notes": ""},
    {"name": "Philip Vigil", "email": "philipvigil1978@gmail.com", "phone": "+17193419725", "notes": ""},
    {"name": "Christie Cole Phonville", "email": "womackchristie53@gmail.com", "phone": "+17194120883", "notes": ""},
    {"name": "Donna S Green", "email": "greenintherockies@gmail.com", "phone": "+17202167662", "notes": ""},
    {"name": "Tseten", "email": "Tsetenzurkhang121@hotmail.com", "phone": "+15715819587", "notes": ""},
    {"name": "Fredrick Ezeani", "email": "emekaezeani97@gmail.com", "phone": "+17206614321", "notes": ""},
    {"name": "Sherri A Smith", "email": "bluey4246@yahoo.com", "phone": "+17192377113", "notes": ""},
    {"name": "Lyes ouagued", "email": "lyessou303030@gmail.com", "phone": "+17203205803", "notes": ""},
    {"name": "Jerry Davis", "email": "Jedavis7500@gmail.com", "phone": "+17193084167", "notes": ""},
    {"name": "Earlene M. Payne", "email": "early456.ep@gmail.com", "phone": "+17192853294", "notes": ""},
    {"name": "Georgia Mena", "email": "georgiamena@hotmail.com", "phone": "+17208251490", "notes": ""},
    {"name": "Chuck Valenzuela Sr.", "email": "chuckvalenzuela88@gmail.com", "phone": "+16614839610", "notes": ""},
    {"name": "Emma Hodo", "email": "ejh60@netzero.net", "phone": "+19412599547", "notes": ""},
    {"name": "Junie British", "email": "bjune2570@gmail.com", "phone": "+17192038371", "notes": ""},
    {"name": "Maucanda rengei", "email": "mattiashetwick@gmail.com", "phone": "+17207891522", "notes": ""},
    {"name": "Yah Freeman", "email": "yahfreeman80@yahoo.com", "phone": "+12679800420", "notes": ""},
    {"name": "Charlotte Suomie", "email": "charlottesuomie@gmail.com", "phone": "+17202297717", "notes": ""},
    {"name": "Mary Ann Medina", "email": "maryannmedina5@gmail.com", "phone": "+17194157215", "notes": ""},
    {"name": "Zu Hussien", "email": "zumohammed800@gmail.com", "phone": "+13035647161", "notes": ""},
    {"name": "Ayantu muleta", "email": "kiyyu2278@gmail.com", "phone": "+17209539330", "notes": ""},
    {"name": "Conrad Sims Sims", "email": "crad10102@gmail.com", "phone": "+12176194053", "notes": ""},
    {"name": "Veronica Contreras", "email": "luceroveronica126@gmail.com", "phone": "+17197171003", "notes": ""},
    {"name": "Chenelle Lenae Sandoval", "email": "herrin-family@msn.com", "phone": "+17192914235", "notes": ""},
    {"name": "Ursula Martinez", "email": "martinezursulat6871@gmail.com", "phone": "+17203774935", "notes": ""},
    {"name": "Jonathan Martinez", "email": "jonathanbmartinezinc@msn.com", "phone": "+17202071502", "notes": ""},
    {"name": "Courtney McGruder", "email": "rainbowbritedecino@gmail.com", "phone": "+19703795493", "notes": ""},
    {"name": "Barbara Romero", "email": "barbara.izabella2012@gmail.com", "phone": "+17192928893", "notes": ""},
    {"name": "Scott Patrick Selvage", "email": "Scott18selvage@gmail.com", "phone": "+17195699190", "notes": ""},
    {"name": "Melissa Craig", "email": "mizjune.mm@gmail.com", "phone": "+17209845253", "notes": ""},
    {"name": "Nancy Fitzgerald", "email": "Tajk1987@icloud.com", "phone": "+17207741141", "notes": ""},
    {"name": "Gizachew Tiku", "email": "patriciacrim116@gmail.com", "phone": "+17204346528", "notes": ""},
    {"name": "Patricia Crim", "email": "patriciacrim116@gmail.com", "phone": "", "notes": ""},
    {"name": "Rickee Garcia", "email": "rickeegarcia8@gmail.com", "phone": "+17203269614", "notes": ""},
    {"name": "PA Diaab", "email": "Digdug1786@gmail.com", "phone": "+19702034560", "notes": ""},
    {"name": "Louise Carr", "email": "Louisecarr88@gmail.com", "phone": "+17196394493", "notes": ""},
    {"name": "Sue Fisher", "email": "lilbit771@gmail.com", "phone": "+17192335278", "notes": ""},
    {"name": "Desiree Baker- Perkins", "email": "dapbkl3@gmail.com", "phone": "+19703085079", "notes": ""},
    {"name": "Loalee Fifita", "email": "aloha.fifita@yahoo.com", "phone": "+17204298227", "notes": "IJ - Texted and called : no response yet. 10/5. Called again no response 10/9. called no response 10/12. no response 10/17"},
    {"name": "Christy Ann", "email": "annbenavides409@gmail.com", "phone": "+17858211916", "notes": "IJ - Texted and called: no response yet. 10/5. Called again no response, 10/9. no response 10/17."},
    {"name": "Carla Clay", "email": "carlaclay778@gmail.com", "phone": "+17194667024", "notes": "IJ - Texted abd Received an inbound call from Carla Clay, She shared her availability as part-time, 2 to 3 days a week, Monday through Friday, and mentioned she is also available on holidays. She stated that while she does not drive herself, she has reliable transportation through her husband. Carla expressed a preference for working in Colorado Springs over Denver. She has 35 years of experience as a Certified Nursing Assistant (CNA) and also holds a QMAP certification. Carla confirmed she is comfortable with personal care tasks and can pass a background check..."},
    {"name": "Joetta Martinez", "email": "joettamartinez783@gmail.com", "phone": "+17195068713", "notes": "IJ - Texted and called: no response yet. 10/5. Called again no response, 10/9. No response 10/17."},
    {"name": "patricia", "email": "patsysegura16@gmail.com", "phone": "+17193734781", "notes": "IJ - Texted and called: She is available for a full-time weekday morning schedule. She mentioned previously that she worked for Colorado Careassist, and she used to work for Susan.. She stated she has reliable transportation, a valid driver's license, and is comfortable with personal care tasks, though she does not hold a CNA certificate but has 20 years of experience. The caregiver also confirmed she can pass a background check. I have sent her the application."},
    {"name": "Leslie Seidenstricker", "email": "leslieseidenstricker@gmail.com", "phone": "+17196405409", "notes": "IJ - She is available for part-time overnight shifts on Sundays, Tuesdays, and Fridays, including holidays. Leslie has 5 years of experience, no certificate, but mentioned she knows CNA duties. She is familiar with catheters, catheter bags, gait belts, checking blood pressure, and managing oxygen tanks. She is comfortable with personal care, has a valid driver's license and car, and can work in both Denver and Colorado Springs."},
    {"name": "Nyima", "email": "Nyima54@yahoo.com", "phone": "+16129919853", "notes": "IJ - Texted and called : no response yet. 10/3, called again no response 10/5. called again no response, 10/09."},
    {"name": "Angela Atteberry", "email": "Atteberry1981@icloud.com", "phone": "+18173176791", "notes": "IJ - Texted and called: She is available 7 days a week full-time, including holidays, has reliable transportation with a valid driver's license, and 27 years of experience working with seniors (no certificate). She lives in Pueblo, is comfortable with personal care, and can pass a background check. I have sent her the application"},
    {"name": "Kim Conner", "email": "kimm03.kc@gmail.com", "phone": "+17205396537", "notes": "IJ - Texted and called: no response yet. 10/3, Called again no response 10/5, Called again no response, 10/09"},
    {"name": "Linda Walker", "email": "lindamw_lynnw@yahoo.com", "phone": "+13315511029", "notes": "IJ - Texted and called: no response yet. 10/3, Called again no response 10/5. Called again no response, 10/09"},
    {"name": "Tom A Mekan", "email": "mekandoit@gmail.com", "phone": "+17203241998", "notes": "IJ - Texted and called: He is available Monday through Friday, including holidays, and confirmed having reliable transportation and a valid driver's license. While they prefer working in Denver. The candidate has around 15 years of caregiving experience, primarily with personal care for family members with serious health issues, though they do not hold formal CNA or HHA certification. They are comfortable assisting with personal care task and confirmed they can pass a background check. I have sent him application."},
    {"name": "Renee Sanchez", "email": "reneesanchez25@gmail.com", "phone": "+17192144657", "notes": "IJ - Texted and called: She can't work in Denver and COS."},
    {"name": "Lauren Ostoich", "email": "Ostoichlauren@rocketmail.com", "phone": "+17192382013", "notes": "IJ - Texted and called: no response yet. 10/3, called again, no response yet. 10/5. Called again no response, 10/09"},
    {"name": "LalañMenace Rivera Rivera", "email": "garza.lavaughn@gmail.com", "phone": "+17208823622", "notes": "IJ - Texted and called: She is available for Mon - Fri, with 18 years of caregiving experience, expressed interest in part-time weekday work in Denver, has reliable transportation, and can assist with personal care. They no longer hold a CNA license right now, cannot do overnights, but can pass a background check. i have sent her the application."},
    {"name": "Grace Boutiqe", "email": "greisye@yahoo.com", "phone": "+19092526313", "notes": "IJ - Texted and called: no response yet. 10/3 Called again no response yet 10/5. Called again no response, 10/09"},
    {"name": "Randy de la nuez", "email": "randyzaragoza85@gmail.com", "phone": "+17195658651", "notes": "IJ - Texted and called: no response yet. 10/3, 10/4 Called again no response yet 10/5. Called again no response, 10/09."},
    {"name": "Timothy Lee Gatuma", "email": "tgatuma@gmail.com", "phone": "+17203384209", "notes": "IJ - Texted and called: He is available part-time Monday–Friday (12 PM–8 PM) and some weekends, with flexibility to work in Denver weekdays and Colorado Springs in weekends. he has caregiving experience with both younger and older individuals but lack CNA/HHA certification. The candidate has transportation, a driver's license, is comfortable with personal care, and can pass a background check. I sent him the application."},
    {"name": "Jonette Hindi", "email": "heyu_3000@yahoo.com", "phone": "+17199300360", "notes": "IJ - Texted and called: She is available Monday–Friday from 8 AM to 4 PM while her child is in school, with occasional weekend availability but not for holidays or overnight shifts. They have reliable transportation, a valid driver's license, can work in COS, not Denver, and are comfortable with personal care tasks."},
    {"name": "Veronica Reyes", "email": "wonkabarson@gmail.com", "phone": "+17192892910", "notes": "IJ - Texted and called: Right now she's out of availability like 1 or 2 days a week, she'll reach out to us in a few weeks, she said.. But not now."},
    {"name": "Martha L Jeffrey", "email": "mamasgirl201045@gmail.com", "phone": "+17209344383", "notes": "IJ - Texted and called: no response yet. 10/3 Called again no response yet 10/4 Called again no response yet 10/5. Called again no response, 10/09"},
    {"name": "Kibrom Eritrawi", "email": "ykibrom13@yahoo.com", "phone": "+17202996083", "notes": "IJ - Texted and called: the candidate declined the position after receiving a higher offer of $23.50 and 25$ from another company.."},
    {"name": "Francisco", "email": "bubbles915808@gmail.com", "phone": "+13037258628", "notes": "IJ - Texted and called: No response yet. 10/3 Called again, no response yet 10/4. Called again, no response yet 10/5. Called again no response, 10/09"},
    {"name": "Beth Purvis Parker", "email": "mlparkersmom@aol.com", "phone": "+12524528040", "notes": "IJ - Texted and called: She is available four days a week from 9 AM to 3 PM, including holidays, and has reliable transportation with a driver's license. They live in Colorado Springs and are comfortable working in COS, not Denver. The candidate is CNA certified, experienced in personal care task, and can pass a background check."},
    {"name": "Michelle Pahnke-Kearney", "email": "michellekearney72@gmail.com", "phone": "+14235390510", "notes": "Called 10/17.. IJ - She prefers a part-time, on any day. She is available on weekends and holidays, prefers Colorado Springs, and can start on October 17th. She has her own transportation and a driver's license. Michelle has prior caregiving experience in a nursing home and home health and is comfortable performing personal care tasks. The application link will be sent to her, and she will notify us once it is submitted."},
    {"name": "Christina Swetman", "email": "Steeninabean@Gmail.com", "phone": "+17193219764", "notes": "IJ- Called and texted no respond yet. later called several times no response. called 9/26 no response,"},
    {"name": "Sonya Blake", "email": "Bratface3237@gmail.com", "phone": "+17192587892", "notes": "IJ- Called and texted, responded. Will call her again later.. Called 9/26 no response."},
    {"name": "trudi coker", "email": "trudiann2odayz@gmail.com", "phone": "+17196515324", "notes": "Received an inbound call from Candidate Trudi Coker (719) 651-5324: She is available for part-time morning shifts (around 4 hours/day), including holidays. She has experience working with seniors, holds a valid driver's license with transportation, and is comfortable with personal care tasks, but cannot lift over 50 lbs. She does not hold a CNA certificate."},
    {"name": "Lois schroeder", "email": "Loiss1015@yahoo.com", "phone": "+14022903144", "notes": "IJ- Texted and called, went on VM. called 9/26 no response."},
    {"name": "Vicki Garcia", "email": "Vickiloehr80@gmail.com", "phone": "+17192175730", "notes": "IJ- her availability is Mon, tues, Wednesday, she can work 3 to 7 hours a day, and on some weekends she can do holidays. She's CNA certified for 20 years, okay with personal care, has DL, and transportation. I sent her the application"},
    {"name": "Florence Gallegos", "email": "florencegallegosbcffl@gmail.com", "phone": "+17192526824", "notes": "IJ- Called and texted, she's not able to work at COS"},
    {"name": "Tracy Godinez Martinez", "email": "tracyanngm@gmail.com", "phone": "+17196886643", "notes": "IJ - Texted, & Called several times, didn't respond, and the mailbox is full. Called 9/26 no response."},
    {"name": "Monique Archibald", "email": "archibaldmonique@gmail.com", "phone": "+17196649871", "notes": "IJ- Availability full time also can do weekend and Holiday, have transportation and DL, have no certificate but personal experience working with seniors, ok with personal care task, prefer COS."},
    {"name": "Leanne Blackburn", "email": "leannelblackburn@yahoo.com", "phone": "+17199940629", "notes": "IJ - Texted and called several times, went on VM. called 9/26 no response."},
    {"name": "Maria Elena Mirador", "email": "mariaelena_mirador@yahoo.com", "phone": "+19092633728", "notes": "IJ- she confirmed she have CNA and DL. She said live in Pueblo. I informed her we give service in Boulder, Denver and Springs if she can give service there she can apply. She asked for the application form. I have sent her."},
    {"name": "Amanda Greene", "email": "mntmom8404@outlook.com", "phone": "+17192137728", "notes": "IJ- Availability Mon-Fri, has reliable transportation and a valid driver's license, and is open to working in Colorado. They have experience with seniors at Right at Home in Colorado Springs, are CPR certified, and are working on their RVP for disabled children. The candidate is comfortable with personal care tasks and confident about passing a background check. I sent her the application."},
    {"name": "Jennifer Atchison Hunter", "email": "thebirdtree@hotmail.com", "phone": "+17197178309", "notes": "IJ - Texted and called went on VM. Called 9/26 Payrate is not enough for her."},
    {"name": "Edward Duane Jaramillo", "email": "duanejaramillo1@gmail.com", "phone": "+17193203142", "notes": "IJ - Texted and called went on VM. Called 9/26 can't work at COS"},
    {"name": "Jennifer Crouch", "email": "jsncrouch@yahoo.com", "phone": "+17192994798", "notes": "IJ - texted and called no response. 9/26 no response"},
    {"name": "Mellissa Forbes", "email": "mellissaforbes2@gmail.com", "phone": "+14193893063", "notes": "IJ - Texted and called no response. 9/26 no response"},
    {"name": "Saffie Sanyang", "email": "sanyangsaffiek@yahoo.com", "phone": "+12067391725", "notes": "IJ- Availability Part-time, including holidays and weekends. The candidate has reliable transportation, a driver's license, and a CNA certification. and is open to working in Colorado. The candidate is comfortable with personal care tasks and confident about passing a background check. I sent her the application."},
    {"name": "Patti Franklin", "email": "pattipannell08@gmail.com", "phone": "+17193309881", "notes": "IJ - Texted and called no response. 9/26 no response"},
    {"name": "Debbie Garner", "email": "garnerdebbie@ymail.com", "phone": "+17199949280", "notes": "IJ - Texted and called no respose. 9/26 no response"},
    {"name": "Candice Martinez", "email": "oterocollegeuser06@gmail.com", "phone": "+17192816397", "notes": "IJ - She's can do full time able to work weekends and holidays as well, Have DL and transport, prefer COS, can do personal care, Candace stated they have over 15 years of experience in healthcare and caregiving, and possess a CNA certification, although not licensed because she got covid at that time.. I sent her the Application."},
    {"name": "Marilyn Pyles", "email": "msc0822@gmail.com", "phone": "+15409351083", "notes": "IJ - She is available for full-time caregiving after 2 PM on weekdays, all day on Saturdays, and after 2 PM on Sundays. She is comfortable working weekends and holidays, but cannot take overnight shifts due to morning"},
    {"name": "Andrea Garcia", "email": "andrearicketts87@gmail.com", "phone": "+17192467417", "notes": "Hired"},
    {"name": "Meryl Somera Vaughan", "email": "somera.csab@gmail.com", "phone": "+19733427746", "notes": "called and texted no response yet - IJ. 9/26 no response"},
    {"name": "Elyssa Justine Pounds", "email": "eyousey011@gmail.com", "phone": "+16205184495", "notes": "IJ - She said she wants to be only her grandma's caregiver I told her for that your grandmother needs to be our client first.. She took the client support number and said she'll give us a call back once she confirmed with her aunt.."},
    {"name": "Michelle Schnapp", "email": "mrschnapp1981@gmail.com", "phone": "+17198226468", "notes": "IJ - called and texted, She's at the hospital right now expecting a call at 4pm,, Later called her several times no response yet."},
    {"name": "Justin Barke", "email": "justinbarke1977@gmail.com", "phone": "+17202879002", "notes": "Not intrested - IJ 9/26"},
    {"name": "Lorena powers", "email": "Lorenalori.powers@gmail.com", "phone": "+17192255316", "notes": "L/M 09/09 CP"},
    {"name": "Amber Rucker", "email": "dawnamber@gmail.com", "phone": "+17196217149", "notes": "L/M 09/09 CP"},
    {"name": "Shirley Smith", "email": "shirleychreene891@gmail.com", "phone": "+19182919252", "notes": "Looking for an agency that will pay her to take care of her son (medicaid) CP"},
    {"name": "Ida Vigil Cruz", "email": "vigilelaine7@gmail.com", "phone": "+17192899214", "notes": "CNA trained, 20+y exp, FT, has car but no DL, told her I would call her back at the end of the week after reviewing candidates CP"},
    {"name": "Angie Dee Stone", "email": "angstone57@gmail.com", "phone": "+17193346180", "notes": "L/M 09/09 CP"},
    {"name": "Chi Pedigo", "email": "chi.pedigo88@gmail.com", "phone": "+17193189944", "notes": "Rang and then disconnected 09/09 CP"},
    {"name": "Phyllis Masoni", "email": "masoniphyllis2@gmail.com", "phone": "+17192525333", "notes": "Not interested"},
    {"name": "Leslie Williams", "email": "lthwilliams@gmail.com", "phone": "+17192462261", "notes": "Will CB, just sat in for a movie 09/09 CP"},
    {"name": "Kimberlina Lira", "email": "kimberlina060599@gmail.com", "phone": "+17192421920", "notes": "L/M 09/09 CP"},
    {"name": "Rebecca Herzog", "email": "rherzog79@gmail.com", "phone": "+17198226366", "notes": "MB is full 09/09 CP"},
    {"name": "Claudia Wright", "email": "cwclaudiaaz@gmail.com", "phone": "+16195523855", "notes": "Wrong #"},
    {"name": "Pilista Koech", "email": "Pilistakoech@yahoo.com", "phone": "+17196512653", "notes": "Try again later, caller is unavailable 09/09 CP"},
    {"name": "Ashley James", "email": "Honeymustard0554@gmail.com", "phone": "+17197745443", "notes": "L/M 09/09 CP"},
    {"name": "Alison Leigh", "email": "AlisonTisdal@gmail.com", "phone": "+17193233389", "notes": "IJ - Alison Leigh (mentioned she's former CG with Colorado CareAssist) Availability: 2 PM – 6 PM, 3–4 days a week (Tues–Fri), not weekends, some holidays.. CNA, 14 years' experience, has driver's license, prefers to work only in COS. Pay Rate Request: $21/hr → informed her COS rates start at $19 and can go up to $23 based on experience; final discussion with management after application.. Sent her the application form."},
    {"name": "Ivy Streans", "email": "ivystearns2001@gmail.com", "phone": "+17194219524", "notes": "IJ - She can work full time, weekend, holiday, no DL but her sister can drive her to the shift, no experience..can pass the background, ok with personal care..prefer COS."},
    {"name": "Angelica Puch", "email": "puchangieap@gmail.c", "phone": "+14062107486", "notes": "Sent application: Took care of mother stage 4 cancer and grandmother"},
    {"name": "Jerry Davis", "email": "Jedavis7500@gmail.com", "phone": "+17193084167", "notes": "Texted and called -IJ"},
    {"name": "ladonna damron", "email": "ladonna1989johnson@gmail.com", "phone": "+17197176698", "notes": "IJ -She's available for full time, she can do weekend and holiday, she prefer COS, She can pass background check, have DL, Ok with personal care also have experience in Morning star Facility for 3years..."},
    {"name": "Aeris Mobley-Jackson", "email": "Aerisv@yahoo.com", "phone": "+13146963632", "notes": "FT, 20y CNA Exp Sent application 09/3 CP"},
    {"name": "Daphanie Gurule", "email": "daphanieg3@gmail.com", "phone": "+17194370152", "notes": ""},
    {"name": "Leticia Cota Esparza", "email": "lae0929@gmail.com", "phone": "+14085618220", "notes": "Texted and called -IJ, L/M 9/3 CP"},
    {"name": "Elizabeth A. Armstrong", "email": "lizzybikes47@gmail.com", "phone": "+14793919283", "notes": "She joined other company.."},
    {"name": "Noma Sibanda", "email": "nomanyabadza123@gmail.com", "phone": "+17192332421", "notes": "Texted and called -IJ, L/M 9/3 CP"},
    {"name": "Muzette Garcia", "email": "garciamuzette3@gmail.com", "phone": "+17196459088", "notes": "texted and called -IJ, 9/3 Disconnected? CP"},
    {"name": "Maria Gonzalez", "email": "mgpeglezc08@outlook.com", "phone": "+17193695191", "notes": "IJ- She's looking for full time can only work morning, day time, don't work at weekend and holiday, have DL, Can pass background, have CNA training but didn't get the certificate that time she was pregnant, ok with personal care, Right not she's working as caregiver's."},
    {"name": "Christine Wagers", "email": "missyb622@yahoo.com", "phone": "+17205195041", "notes": "She can do full time, also available to work holidays and weekends, has reliable transportation, a valid driver's license, and is comfortable working in Colorado Springs. Ok with Personal care task.. William to learn.. have personal experience with a family member who has Alzheimer's and also has diabetes. Sent her the Application."},
    {"name": "Karina Rivera Castel", "email": "karcas2006@gmail.com", "phone": "+17192167318", "notes": "Texted and called -IJ, L/M 9/3 CP"},
    {"name": "Lacee Barna-Bessette", "email": "lp.ny327@aol.com", "phone": "+15188219082", "notes": "IJ- She can do Full time, weekend, holiday, location COS, have DL, 12 years of working with seniors no certificate, she can take care of the seniors and also housekeeping but can't lift them.."},
    {"name": "Layna Simms", "email": "ladyjane01sim11lay@yahoo.com", "phone": "+17194596642", "notes": "CNA trained, FT, in chool for psychiatry, quoted $20/hr, sent application 9/3 CP"},
    {"name": "Nicole Shelhammer", "email": "shelhammer14@gmail.com", "phone": "+17193200388", "notes": "IJ- availability Full time, Weekend and Holiday. She volunteered at nursing homes and willing to learn taking care of seniors. She's ok with personal care task. Have reliable transportation, a valid driver's license, Prefer COS. The candidate confirmed they could pass a background check but had a DUI in 2022, which is now resolved. She can start as early as possible."},
    {"name": "Julie Singletary", "email": "julzd12c@gmail.com", "phone": "+17196296958", "notes": "Texted and called -IJ, L/M 9/3 CP"},
    {"name": "Monica Diaz", "email": "nanibooboo23@gmail.com", "phone": "+17195691884", "notes": "Not intrested - IJ"},
    {"name": "Chrissy Kay", "email": "Christalkay52@gmail.com", "phone": "+17205278731", "notes": "IJ -She's not available today 8/24. She'll be available for a phone conversation tomorrow 8/25 at noon. L/M 9/3 CP"},
    {"name": "Joe Barrera", "email": "jjbarr46@gmail.com", "phone": "+17194327247", "notes": "Not intrested - IJ"},
    {"name": "Angel Adams", "email": "sikkle53@gmail.com", "phone": "+17193326915", "notes": "IJ - Replied message that she's in Church right now. She'll available for phone screening on Monday after 1pm., 9/3 will cb after 2:30p"},
    {"name": "Rachael Bautzmann", "email": "bautzmannrachael9@gmail.com", "phone": "+16039578939", "notes": "Hired"},
    {"name": "Shalonda Andrews", "email": "shay19800308@gmail.com", "phone": "+17195571651", "notes": "She has open availabilty, has car and DL, she prefers to work in COS, has 18 years caregiving experience, she preferred to work in COS, at least $20-21, can START ASAP"},
    {"name": "Jennifer Deal Bates", "email": "jennabl2@yahoo.com", "phone": "+18636086447", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Mandie Wine", "email": "mandawine7@gmail.com", "phone": "+17193097807", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Shirley Smith", "email": "shirleychreene891@gmail.com", "phone": "+19182919252", "notes": "Lives in Pueblo. Exp CG, currently working with another agency"},
    {"name": "Kaylee Victoria Wolf", "email": "babyg82102@gmail.com", "phone": "+17197226871", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Carol Jean Martinez", "email": "carol.martinez101@icloud.com", "phone": "+14059060440", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Roberta", "email": "bervec@gmail.com", "phone": "+17197289071", "notes": "wrong number - FC"},
    {"name": "Kelly lopez", "email": "kelly.lopez81@outlook.com", "phone": "+13607427833", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Philip Vigil", "email": "philipvigil1978@gmail.com", "phone": "+17193419725", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Dawn michelle Barker", "email": "dawnbarker97@gmail.com", "phone": "+17192443418", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Sarah Roscow Trujillo", "email": "trujillo1971@gmail.com", "phone": "+16189751604", "notes": "HIRED 09/04"},
    {"name": "Jessica A Rothermund", "email": "Jrother0823@gmail.com", "phone": "+17196661225", "notes": "HIRED 08/18"},
    {"name": "Elyssa Justine Pounds", "email": "eyousey011@gmail.com", "phone": "+16205184495", "notes": "Takes care of grandmother who has medicaid, wanted to sign up so she can get paid"},
    {"name": "Kandis Keys", "email": "gingerredd78@gmail.com", "phone": "+17192179264", "notes": "HIRED 08/18"},
    {"name": "Luzelena Bustos", "email": "luzi.bustos@gmail.com", "phone": "+17192919781", "notes": "NIS"},
    {"name": "Angie Dee Stone", "email": "angstone57@gmail.com", "phone": "+17196718707", "notes": "NIS"},
    {"name": "Ruben Soto III", "email": "rubensnewemail77@gmail.com", "phone": "+17192290120", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Wendy Skog", "email": "tickywench@gmail.com", "phone": "+17194391324", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Angelica Frederick", "email": "angelica.fernandez0816@yahoo.com", "phone": "+17197287820", "notes": "PT (sunday 8a-5p, mon 10a-3p, tues 10a-3p), COS, 6+y exp, CNA &QMAP, wants $20-$25, L/M 9/3 CP"},
    {"name": "Alana Espinoza", "email": "alana.moni_17@outlook.com", "phone": "+17197716711", "notes": "She's not inrerested. - FC"},
    {"name": "Brandy Edwards", "email": "brandymedwards360@gmail.com", "phone": "+15399950611", "notes": "She has open availabilty, has car and DL, she prefers to work in COS, has 15 years caregiving experience, ok between $19-$20"},
    {"name": "beatrix millek", "email": "Bmillek@yahoo.com", "phone": "+13373537070", "notes": "Will call us back - FC, L/M 9/3 CP"},
    {"name": "Jason Beagley", "email": "beagley69@gmail.com", "phone": "+15033809709", "notes": "not interested"},
    {"name": "Manda Dawn Packard", "email": "mandapackard75@gmail.com", "phone": "+17196519344", "notes": "called and texted - FC, voicemail not set up 9/3 CP"},
    {"name": "Antonio Dersno", "email": "antoniodersno107@gmail.com", "phone": "+17196445840", "notes": "Works FT for trash co, took care of his mother, wants PT, $20/h, asked for some time to think it over 9/3 CP"},
    {"name": "Reed Arin", "email": "arinreed.83@gmail.com", "phone": "+17196210606", "notes": "called and texted - FC, L/M 9/3 CP"},
    {"name": "Lizbeth Ortiz vila", "email": "lortizvila@gmail.com", "phone": "+17193444459", "notes": "called and texted - FC, Hung up?....9/2 CP"},
    {"name": "Joann Slayden", "email": "jslayden89@gmail.com", "phone": "+13109445329", "notes": "called and texted - FC, L/M 9/2"},
    {"name": "Christina Abila", "email": "Christinabila64@gmail.com", "phone": "+17193009695", "notes": "Texted and called - IJ, Sent app, Exp CG and QMAP, part time, COS 9/2 CP"},
    {"name": "Rosie Hendricks", "email": "hendricks_rosie@yahoo.com", "phone": "+17193702473", "notes": "Texted and called - IJ, L/M 9/2 CP"},
    {"name": "Melissa Ortiz", "email": "mellyeli57@gmail.com", "phone": "+17194963132", "notes": "HIRED 08/18: Terminated 08/20 NO DL"},
    {"name": "Sheila Vanzandt", "email": "1nyer4ever@gmail.com", "phone": "+13033564156", "notes": "responded. She's going out of State for an extended period soon. She will contact when she return."},
    {"name": "Jerry Salazar", "email": "jrtoronto2007@msn.com", "phone": "+17192896350", "notes": "not comfortable with personal care and housekeeping."},
    {"name": "Kimberly Holbert", "email": "kimberly_holbert@yahoo.com", "phone": "+17194660974", "notes": "Texted and called - IJ, Sent application, Exp CG, will work Denver and COS 9/2 CP"},
    {"name": "Daniel Galindo", "email": "danielgalindo032@gmail.com", "phone": "+12108478755", "notes": "not interested in private company"},
    {"name": "Lola Marable", "email": "lolamarable9@gmail.com", "phone": "+18508966003", "notes": "Texted and called - IJ, L/M 9/2 CP, sent application, EXP caregiver 9/2 CP"},
    {"name": "Kimberlee D Kennedy", "email": "kimkennedy284@gmail.com", "phone": "+17196272578", "notes": "Texted and called - IJ, L/M 9/2 CP"},
    {"name": "Gina Valdez", "email": "valdezgina305@gmail.com", "phone": "+17197161091", "notes": "Replied but didn't received the call -IJ, L/M 9/2 CP"},
    {"name": "Jill Jantzen", "email": "Jilljantzen@gmail.com", "phone": "+17195940678", "notes": "called and texted - FC, Sent application (looking for PT, took care of family member for years-9/2 CP)"},
    {"name": "Brooke Nicole", "email": "bkelley000046@gmail.com", "phone": "+16064001544", "notes": "called and texted - FC, L/M 9/2 CP"},
    {"name": "Desiree Atencio", "email": "may61desi.com@gmail.com", "phone": "+17194824467", "notes": "called and texted - FC, L/M 9/2 CP"},
    {"name": "Chelsie Brentlinger", "email": "Chelsiebrentlinger@gmail.com", "phone": "+17196887932", "notes": "called and texted - FC, L/M 9/2 CP voicemail says Jennett"},
    {"name": "Debbie Garner", "email": "garnerdebbie@ymail.com", "phone": "+17199949280", "notes": "called and texted - FC, L/M 9/2 CP Sent application, Exp CG, Overnights, Pueblo 9/2 CP)"},
    {"name": "Edward Duane Jaramillo", "email": "duanejaramillo1@gmail.com", "phone": "+17193203142", "notes": "called and texted - FC, lives in Pueble, not interested in commute"},
    {"name": "Anneliese Mann Martin", "email": "anneliesemartin@usa.net", "phone": "+17192905876", "notes": "HIRED 08/18, Quit"},
    {"name": "Samantha Spirit", "email": "sjdani2006@gmail.com", "phone": "+17198675309", "notes": "called and texted - FC, L/M 9/2 CP"},
    {"name": "Jeremy Richard Turney", "email": "jeremyturney5150@gmail.com", "phone": "+17193629534", "notes": "called and texted - FC, Sent application (looking for PT, took care of family member for years-9/2 CP)"},
    {"name": "Jikyla Harris", "email": "jikylah1089@gmail.com", "phone": "+17162569421", "notes": "She has open availability except Saturday 8am-4pm, has car and DL, located in Pueblo, has 3 years caregiver of her grandmother. L/M 9/2 CP"},
    {"name": "Angela Weiss Howard", "email": "angelalivelovelaugh@gmail.com", "phone": "+12392894909", "notes": "called and texted - FC, L/M 9/2 CP"},
    {"name": "Amanda Maloof", "email": "1love1life.4cdef@gmail.com", "phone": "+17197663382", "notes": "called and texted - FC, L/M 9/2 CP"},
    {"name": "Beverly Thomas", "email": "beverlyv66@gmail.com", "phone": "+17193067807", "notes": "called and texted - FC, (will call back at 330p CP 9/2)"},
    {"name": "shalonda Crowder", "email": "lashawn.crowder1993@gmail.com", "phone": "+17193545582", "notes": "called and texted - FC, L/M 9/2 CP"},
    {"name": "Jrocc Vince", "email": "jroccvince@gmail.com", "phone": "+17192018374", "notes": "called and texted - FC"},
]

def import_leads():
    with app.app_context():
        # Clear existing leads
        Lead.query.delete()
        db.session.commit()
        
        # Get default users for assignment
        users = User.query.all()
        default_user = users[0] if users else None
        
        leads_added = 0
        
        # Process leads in reverse order so newest leads get highest IDs
        for lead_data in reversed(leads_data):
            # Skip leads with empty phone numbers
            if not lead_data['phone'] or lead_data['phone'].strip() == '':
                print(f"Skipping lead with empty phone: {lead_data['name']}")
                continue
            
            # Clean phone number
            phone = clean_phone(lead_data['phone'])
            
            # Skip if phone is still empty after cleaning
            if not phone:
                print(f"Skipping lead with invalid phone: {lead_data['name']}")
                continue
            
            # Check for existing lead to prevent duplicates
            existing_lead = Lead.query.filter_by(phone=phone).first()
            if existing_lead:
                print(f"Skipping duplicate lead: {lead_data['name']} ({phone})")
                continue
            
            # Determine status from notes
            status = determine_status_from_notes(lead_data['notes'])
            
            # Create lead (set to unassigned initially)
            lead = Lead(
                name=lead_data['name'],
                email=lead_data['email'],
                phone=phone,
                notes=lead_data['notes'],
                status=status,
                assigned_to=None  # Set to unassigned initially
            )
            
            db.session.add(lead)
            leads_added += 1
        
        db.session.commit()
        print(f"Successfully imported {leads_added} leads from Google Sheet!")

if __name__ == "__main__":
    import_leads()
