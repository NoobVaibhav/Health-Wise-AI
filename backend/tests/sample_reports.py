"""Invented reports of many kinds (no real patient data), used to check that the analysis understands each of them."""

ECHO = """CITY HEART INSTITUTE - DEPARTMENT OF CARDIOLOGY
2D ECHOCARDIOGRAPHY WITH COLOUR DOPPLER REPORT
Patient Name: Rahul Patil    Age/Sex: 58 / M    Date: 12/03/2026
Referred by: Dr. A. Sharma
M-MODE MEASUREMENTS
LVIDd 5.8 cm   LVIDs 4.6 cm   IVSd 1.1 cm   LVPWd 1.0 cm
LA 4.2 cm   Aortic root 3.1 cm
LVEF 35 %
FINDINGS
Left ventricle is dilated with global hypokinesia. Regional wall motion abnormality noted in the anterior wall and septum.
Mitral valve: moderate mitral regurgitation. Aortic valve: trileaflet, no aortic stenosis, trivial aortic regurgitation.
Tricuspid valve: mild tricuspid regurgitation. RVSP 48 mmHg.
Grade II diastolic dysfunction. No pericardial effusion. No clot or vegetation seen. IVC is normal in size.
IMPRESSION
1. Dilated left ventricle with severe LV systolic dysfunction, LVEF 35%.
2. Moderate mitral regurgitation.
3. Mild pulmonary hypertension.
Clinical correlation is advised.
"""

ANGIO = """HEART CARE HOSPITAL - CATH LAB
CORONARY ANGIOGRAPHY REPORT
Patient: Hari Lad   Age/Sex: 62 / M   Date: 05/02/2026
Access: Right radial artery
FINDINGS
Left main coronary artery: normal.
LAD: proximal LAD 90% stenosis, mid LAD 70% stenosis. TIMI II flow.
LCX: ostial LCX 50% stenosis. OM1 small, normal.
RCA: dominant, mid RCA 100% chronic total occlusion with collaterals. Right dominant system.
LV gram: EF 40%.
IMPRESSION
Double vessel coronary artery disease (LAD and RCA) with significant proximal LAD disease.
ADVICE
PTCA with stenting to LAD is advised. Surgical opinion for CABG may be considered. Continue dual antiplatelet therapy.
"""

CT = """CITY DIAGNOSTIC CENTRE
CT SCAN CHEST (PLAIN AND CONTRAST)
Patient Name: Sunita Kale   Age/Sex: 54 / F   Date: 09/01/2026
CLINICAL HISTORY: Persistent cough for six weeks.
TECHNIQUE: Axial sections of the chest were obtained after intravenous contrast.
FINDINGS
A spiculated nodule measuring 2.1 x 1.8 cm is seen in the right upper lobe. Few enlarged right paratracheal lymph nodes, largest 1.4 cm.
Mild right pleural effusion. No pneumothorax. Heart size is normal. No bony lesion.
IMPRESSION
Right upper lobe spiculated nodule with mediastinal lymphadenopathy, suspicious for malignancy. Biopsy is advised.
"""

XRAY = """SUNRISE DIAGNOSTICS
X-RAY CHEST PA VIEW
Patient Name: Amit Joshi   Age/Sex: 41 / M   Date: 15/02/2026
FINDINGS
Homogeneous opacity is seen in the right lower zone with blunting of the right costophrenic angle.
Cardiothoracic ratio is 0.52. Trachea is central. Both hila are normal. No bony abnormality.
IMPRESSION
Right lower zone consolidation with small pleural effusion. Clinical correlation advised.
"""

XRAY_NORMAL = """X-RAY CHEST PA VIEW
Patient Name: Neha Rao
FINDINGS
Both lung fields are clear. Cardiothoracic ratio is 0.46. Costophrenic angles are clear. Bony thorax is normal.
IMPRESSION
Normal chest radiograph.
"""

MRI = """MRI LUMBAR SPINE
Patient Name: Vikas Pawar   Age/Sex: 47 / M
FINDINGS
Loss of normal lumbar lordosis. L4-L5 disc shows posterior bulge with moderate canal stenosis and bilateral neural foraminal narrowing.
L5-S1 disc desiccation with a left paracentral protrusion compressing the traversing S1 nerve root.
Conus medullaris ends at L1 level. No marrow oedema.
IMPRESSION
L4-L5 disc bulge with moderate canal stenosis. L5-S1 left paracentral disc protrusion with S1 nerve root compression.
"""

USG = """ULTRASOUND ABDOMEN AND PELVIS
Patient Name: Meena Shah   Age/Sex: 36 / F
FINDINGS
Liver is enlarged (16.8 cm) with raised echotexture, suggestive of grade II fatty liver. Gall bladder shows a 9 mm calculus. CBD is normal.
Spleen is normal (10.2 cm). Both kidneys are normal in size. Uterus and ovaries are normal. No free fluid.
IMPRESSION
Grade II fatty liver. Cholelithiasis.
"""

TMT = """TREADMILL TEST (TMT) REPORT
Patient Name: Ravi Desai   Age/Sex: 55 / M
Protocol: Bruce. Exercise time 6 min 30 sec. Resting HR 78 bpm. Peak HR 142 bpm (85 % of maximum predicted heart rate 165 bpm). Peak BP 170/90 mmHg. Achieved METs 7.0
Test stopped due to fatigue. ST segment depression of 2.1 mm in leads V4-V6 at peak exercise, persisting 4 minutes into recovery. Chest pain at peak exercise.
IMPRESSION
TMT is positive for inducible myocardial ischaemia.
"""

PFT = """PULMONARY FUNCTION TEST (SPIROMETRY)
Patient Name: Kiran Nair   Age/Sex: 60 / M
FVC 3.10 L (82 % predicted)   FEV1 1.45 L (48 % predicted)   FEV1/FVC 47 %   PEF 3.9 L/s
IMPRESSION
Moderate to severe obstructive ventilatory defect. No significant bronchodilator response.
"""

DEXA = """BONE MINERAL DENSITY (DEXA) REPORT
Patient Name: Asha Kulkarni   Age/Sex: 63 / F
Lumbar spine L1-L4 T-score -2.8   Z-score -1.9
Femoral neck T-score -2.1
IMPRESSION
Osteoporosis at the lumbar spine. Osteopenia at the femoral neck.
"""

ALL = {"ECHO": ECHO, "ANGIO": ANGIO, "CT": CT, "XRAY": XRAY, "XRAY_NORMAL": XRAY_NORMAL, "MRI": MRI, "USG": USG, "TMT": TMT, "PFT": PFT, "DEXA": DEXA}
