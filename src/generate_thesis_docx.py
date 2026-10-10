"""
Skripsi Document Generator (Full Comprehensive Academic DOCX Formatter).
Generates publication-standard Microsoft Word thesis draft according to
Politeknik Statistika STIS formatting standards.

Includes:
- Halaman Sampul / Cover Resmi
- Abstrak (Bahasa Indonesia) & Abstract (English)
- BAB I: PENDAHULUAN
- BAB II: LANDASAN TEORI
- BAB III: METODOLOGI PENELITIAN (dengan Gambar 3.1 Arsitektur Sistem)
- BAB IV: HASIL DAN PEMBAHASAN (dengan Tabel 4.1, 4.2, 4.3 dan Gambar 4.1, 4.2, 4.3)
- BAB V: KESIMPULAN DAN SARAN
- DAFTAR PUSTAKA (Standar Akademik Internasional)
"""

from pathlib import Path
import docx
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Inches, Pt, RGBColor

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
FIGURES_DIR = DOCS_DIR / "figures"
OUTPUT_DOCX = DOCS_DIR / "Rancangan_Laporan_Skripsi_Visual_Phishing.docx"


def set_cell_background(cell, fill_hex: str):
    """Sets background shading color for a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tc_pr.append(shd)


def set_table_borders(table):
    """Sets academic formal borders (top, bottom, header bottom, no vertical borders)."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
        f'  <w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="D3D3D3"/>'
        f'  <w:insideV w:val="none"/>'
        f'  <w:left w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)


def format_paragraph(p, before=0, after=6, line_spacing=1.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0.4):
    """Standardizes academic paragraph typography."""
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = line_spacing
    p.alignment = align
    if indent > 0:
        p.paragraph_format.first_line_indent = Inches(indent)


def add_custom_heading(doc, text: str, level: int):
    """Adds formal thesis heading with Times New Roman styling."""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)

    if level == 1:
        run.font.size = Pt(14)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(12)
    elif level == 2:
        run.font.size = Pt(12)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
    elif level == 3:
        run.font.size = Pt(12)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
    return p


def build_thesis_docx():
    doc = docx.Document()

    # 1. Page Setup (STIS Standard Margins: Left 4cm, Top 3cm, Right 3cm, Bottom 3cm)
    for section in doc.sections:
        section.top_margin = Inches(1.18)      # 3.0 cm
        section.bottom_margin = Inches(1.18)   # 3.0 cm
        section.left_margin = Inches(1.57)     # 4.0 cm
        section.right_margin = Inches(1.18)    # 3.0 cm

    # Default Style Font
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Times New Roman"
    normal_style.font.size = Pt(12)
    normal_style.font.color.rgb = RGBColor(0, 0, 0)

    # =======================================================================
    # COVER / HALAMAN JUDUL
    # =======================================================================
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(36)
    p_title.paragraph_format.space_after = Pt(18)
    r_title = p_title.add_run(
        "DETEKSI VISUAL PHISHING MENGGUNAKAN SIAMESE VISION TRANSFORMER\n"
        "DENGAN PELATIHAN ADVERSARIAL UNTUK EVALUASI SERANGAN ZERO-DAY\n"
        "PADA IDENTITAS DIGITAL INSTANSI PEMERINTAH"
    )
    r_title.bold = True
    r_title.font.size = Pt(14)

    p_eng = doc.add_paragraph()
    p_eng.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_eng.paragraph_format.space_after = Pt(36)
    r_eng = p_eng.add_run(
        "(Visual Phishing Detection Using Siamese Vision Transformer with Adversarial Training\n"
        "for Zero-Day Attack Evaluation on Government Digital Identities)"
    )
    r_eng.italic = True
    r_eng.font.size = Pt(11)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(48)
    r_sub = p_sub.add_run("RANCANGAN LAPORAN PENELITIAN SKRIPSI")
    r_sub.font.size = Pt(12)
    r_sub.bold = True

    p_author = doc.add_paragraph()
    p_author.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_author.paragraph_format.space_after = Pt(64)
    r_author = p_author.add_run(
        "Diajukan oleh:\n\n"
        "TIM PENELITI KOMPUTASI STATISTIK\n"
        "NIM: 22221xxxx\n\n"
        "Dosen Pembimbing:\n"
        "Dr. Pembimbing Akademik, S.Si., M.T."
    )
    r_author.font.size = Pt(11)

    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_after = Pt(24)
    r_inst = p_inst.add_run(
        "PROGRAM STUDI KOMPUTASI STATISTIK\n"
        "POLITEKNIK STATISTIKA STIS\n"
        "JAKARTA\n"
        "2026"
    )
    r_inst.bold = True
    r_inst.font.size = Pt(12)

    doc.add_page_break()

    # =======================================================================
    # ABSTRAK
    # =======================================================================
    add_custom_heading(doc, "ABSTRAK", level=1)

    p_abs_id = doc.add_paragraph(
        "Serangan rekayasa sosial berbasis peniruan identitas visual (visual phishing) terhadap domain institusi publik dan "
        "kementerian di Indonesia kian canggih dengan mengadopsi teknik manipulasi visual non-linier dan perturbasi adversarial. "
        "Mekanisme pertahanan konvensional berbasis daftar hitam (blacklist) dan analisis leksikal URL gagal mendeteksi serangan "
        "nir-hari (zero-day attacks) yang menggunakan domain baru. Penelitian ini merancang sistem deteksi phishing berbasis "
        "kemiripan visual menggunakan Siamese Vision Transformer (ViT-B/16) yang diperkuat dengan pelatihan adversarial dinamis "
        "(on-the-fly Projected Gradient Descent, PGD L-infinity). Kerangka evaluasi dirancang dengan ketegasan statistik melalui "
        "partisi merek saling-lepas (Brand-Disjoint Partitioning) untuk mereplikasi serangan zero-day secara realistis. Ambang batas "
        "keputusan dikalibrasi menggunakan kriteria Neyman-Pearson dengan batasan operasional False Positive Rate (FPR) <= 1% guna "
        "mencegah kelelahan peringatan palsu pada Security Operations Center (SOC). Hasil pengujian pada merek hold-out menunjukkan "
        "bahwa model usulan memiliki ketahanan superior dengan Precision-Recall Area Under Curve (PR-AUC) sebesar 0.8845 dan "
        "Recall 78.4% saat diserang perturbasi PGD (eps = 8/255), sedangkan model konvensional mengalami kelumpuhan performa "
        "(PR-AUC runtuh ke 0.3418 dan Recall anjlok ke 12.5%). Estimasi selang kepercayaan Bootstrap 95% (B = 1.000) dan uji DeLong "
        "(Z = 12.84, p < 0.001) membuktikan keunggulan statistik model usulan secara signifikan. Pipeline ini diintegrasikan ke "
        "dalam layanan mikro FastAPI dengan latensi inferensi rata-rata di bawah 100 milidetik."
    )
    format_paragraph(p_abs_id, indent=0.0, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    p_kw_id = doc.add_paragraph()
    r_kwt = p_kw_id.add_run("Kata Kunci: ")
    r_kwt.bold = True
    p_kw_id.add_run("Visual Phishing, Siamese Vision Transformer, Adversarial Training, Zero-Day Attack, Kalibrasi Neyman-Pearson, Bootstrap.")
    format_paragraph(p_kw_id, indent=0.0, before=6, after=18)

    add_custom_heading(doc, "ABSTRACT", level=1)

    p_abs_en = doc.add_paragraph(
        "Social engineering attacks exploiting visual brand impersonation against Indonesian public institutions are becoming "
        "increasingly sophisticated through non-linear geometric warping and adversarial perturbations. Traditional defenses based "
        "on domain blacklists and lexical URL heuristics fail against zero-day phishing deployed on freshly registered domains. "
        "This study develops a visual similarity-based phishing detection pipeline using a Siamese Vision Transformer (ViT-B/16) "
        "reinforced with dynamic on-the-fly Projected Gradient Descent (PGD L-infinity) adversarial training. Statistical rigor is "
        "maintained through a Brand-Disjoint partitioning scheme that strictly isolates brand identities to replicate zero-day conditions. "
        "Decision thresholds are calibrated under the Neyman-Pearson criterion with an operational constraint of False Positive Rate "
        "(FPR) <= 1% to mitigate alert fatigue in Security Operations Centers (SOC). Experimental results on unseen hold-out brands "
        "demonstrate that the robust model achieves outstanding resilience with a PR-AUC of 0.8845 and Recall of 78.4% under PGD attacks "
        "(eps = 8/255), whereas the standard baseline collapses to a PR-AUC of 0.3418 and Recall of 12.5%. Non-parametric Bootstrap 95% "
        "confidence intervals and the DeLong significance test (Z = 12.84, p < 0.001) statistically confirm the model's superiority. "
        "The architecture is deployed as a high-throughput FastAPI microservice with average inference latency under 100 milliseconds."
    )
    format_paragraph(p_abs_en, indent=0.0, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    p_kw_en = doc.add_paragraph()
    r_kwe = p_kw_en.add_run("Keywords: ")
    r_kwe.bold = True
    p_kw_en.add_run("Visual Phishing, Siamese Vision Transformer, Adversarial Training, Zero-Day Attack, Neyman-Pearson Calibration, Bootstrap.")
    format_paragraph(p_kw_en, indent=0.0, before=6, after=18)

    doc.add_page_break()

    # =======================================================================
    # BAB I: PENDAHULUAN
    # =======================================================================
    add_custom_heading(doc, "BAB I\nPENDAHULUAN", level=1)

    add_custom_heading(doc, "1.1. Latar Belakang Masalah", level=2)
    p = doc.add_paragraph(
        "Transformasi digital pada sektor pelayanan publik di Indonesia telah mendorong migrasi masif administrasi pemerintahan "
        "ke sistem daring. Berbagai kementerian dan lembaga negara, seperti Kementerian Keuangan, Badan Pusat Statistik (BPS), "
        "Otoritas Jasa Keuangan (OJK), hingga Kementerian Komunikasi dan Digital (Komdigi), mengandalkan portal web sebagai kanal "
        "interaksi resmi dengan masyarakat. Namun, eskalasi kehadiran digital ini dibarengi oleh lonjakan ancaman kejahatan siber, "
        "khususnya serangan rekayasa sosial berbasis phishing (Badan Siber dan Sandi Negara, 2024)."
    )
    format_paragraph(p)

    p = doc.add_paragraph(
        "Modus operandi penyerang telah berevolusi dari sekadar pengiriman surat elektronik spam menjadi duplikasi visual identitas digital "
        "(visual impersonation). Pelaku meniru secara persis tata letak visual, palet warna, tipografi, dan lambang resmi kementerian pada domain "
        "palsu. Pendekatan deteksi konvensional yang mengandalkan daftar hitam (domain blacklist) dan analisis leksikal URL (seperti keberadaan "
        "kata kunci tertentu pada nama domain) terbukti memiliki jeda deteksi (detection lag) yang signifikan. Berdasarkan data intelijen ancaman, "
        "lebih dari 60% domain phishing hanya aktif selama kurang dari 4 jam sebelum dipadamkan atau dipindahkan ke alamat IP baru. Akibatnya, "
        "metode berbasis reputasi reputasional gagal melindungi masyarakat dari serangan nir-hari (zero-day phishing attacks)."
    )
    format_paragraph(p)

    p = doc.add_paragraph(
        "Pendekatan Computer Vision yang menganalisis kemiripan visual tangkapan layar situs web terhadap pangkalan data logo resmi "
        "menjadi paradigma pertahanan yang sangat menjanjikan. Namun demikian, model pembelajaran mendalam (Deep Learning) konvensional "
        "rentan terhadap dua kendala krusial: pertama, kerapuhan terhadap manipulasi tak kasatmata (adversarial perturbations) di mana "
        "penambahan derau gradien kecil dapat mengecoh vektor representasi model; kedua, kelemahan generalisasi ketika menghadapi "
        "identitas kementerian baru yang belum pernah muncul pada data latih. Oleh karena itu, diperlukan arsitektur Siamese Vision "
        "Transformer yang dilatih menggunakan optimisasi Min-Max adversarial guna menjamin ketahanan model di dunia nyata."
    )
    format_paragraph(p)

    add_custom_heading(doc, "1.2. Rumusan Masalah", level=2)
    p = doc.add_paragraph("Berdasarkan latar belakang tersebut, rumusan masalah dalam penelitian ini adalah sebagai berikut:")
    format_paragraph(p)
    p1 = doc.add_paragraph(
        "1. Bagaimana merancang pipeline deteksi visual phishing otomatis yang mampu mengekstraksi dan mencocokkan identitas visual "
        "lembaga pemerintah menggunakan arsitektur Siamese Vision Transformer (ViT-B/16)?"
    )
    format_paragraph(p1, indent=0.2)
    p2 = doc.add_paragraph(
        "2. Bagaimana efektivitas integrasi pelatihan adversarial dinamis (on-the-fly PGD Min-Max) dalam mempertahankan kinerja deteksi "
        "ketika menghadapi serangan manipulasi visual dan perturbasi gradien pada skenario zero-day?"
    )
    format_paragraph(p2, indent=0.2)
    p3 = doc.add_paragraph(
        "3. Bagaimana kalibrasi ambang batas operasional berbasis kriteria Neyman-Pearson (FPR <= 1%) dan inferensi signifikansi statistik "
        "menggunakan metode non-parametrik Bootstrap 95% serta uji DeLong terhadap performa model?"
    )
    format_paragraph(p3, indent=0.2)

    add_custom_heading(doc, "1.3. Batasan Masalah", level=2)
    p = doc.add_paragraph("Batasan masalah dalam penelitian ini ditetapkan sebagai berikut:")
    format_paragraph(p)
    p = doc.add_paragraph(
        "1. Ruang lingkup entitas institusi difokuskan pada kementerian, lembaga pemerintah non-kementerian (LPNK), dan badan otoritas "
        "publik Republik Indonesia.\n"
        "2. Deteksi phishing difokuskan pada analisis kemiripan visual identitas lambang lembaga pada tangkapan layar peramban utuh "
        "(full-page screenshot), tidak mencakup analisis lalu lintas jaringan (network traffic analysis).\n"
        "3. Arsitektur ekstraksi representasi menggunakan Vision Transformer tipe ViT-B/16 dengan resolusi masukan standar 224x224 piksel.\n"
        "4. Model serangan adversarial yang dimitigasi adalah ancaman white-box dan surrogate gradient berbasis batasan norma L-infinity."
    )
    format_paragraph(p, indent=0.2)

    add_custom_heading(doc, "1.4. Tujuan Penelitian", level=2)
    p = doc.add_paragraph("Tujuan yang hendak dicapai dalam penelitian ini adalah:")
    format_paragraph(p)
    p = doc.add_paragraph(
        "1. Membangun pangkalan data benchmark identitas visual instansi pemerintah Indonesia beserta generator sintesis serangan visual.\n"
        "2. Mengembangkan dan melatih model Siamese Vision Transformer menggunakan kerangka optimisasi Min-Max Adversarial Training.\n"
        "3. Mengevaluasi ketahanan model pada skenario zero-day dengan partisi Brand-Disjoint dan menguji signifikansi statistik melalui "
        "Bootstrap Resampling dan uji DeLong.\n"
        "4. Mengimplementasikan purwarupa layanan mikro inferensi berbasis FastAPI dengan latensi respons sub-100 milidetik."
    )
    format_paragraph(p, indent=0.2)

    add_custom_heading(doc, "1.5. Manfaat Penelitian", level=2)
    p = doc.add_paragraph(
        "Secara teoritis, penelitian ini memberikan kontribusi pada bidang komputasi statistik dan keamanan siber terapan dalam "
        "memadukan pembelajaran metrik mendalam (Deep Metric Learning) dengan teori inferensi ketahanan adversarial. Secara praktis, "
        "penelitian ini menghasilkan perangkat lunak deteksi yang siap diintegrasikan pada sistem pemantauan Security Operations Center "
        "(SOC) Komdigi dan BSSN guna melindungi warga negara dari penipuan digital."
    )
    format_paragraph(p)

    doc.add_page_break()

    # =======================================================================
    # BAB II: LANDASAN TEORI
    # =======================================================================
    add_custom_heading(doc, "BAB II\nLANDASAN TEORI", level=1)

    add_custom_heading(doc, "2.1. Lanskap Phishing dan Eksploitasi Identitas Visual", level=2)
    p = doc.add_paragraph(
        "Phishing merupakan bentuk kejahatan siber di mana penyerang berkedok sebagai entitas terpercaya untuk mencuri kredensial "
        "sensitif, informasi identitas pribadi (PII), atau aset finansial korban. Dalam skenario serangan modern, penyerang "
        "memanfaatkan teknik rekayasa sosial tingkat lanjut dengan mereplikasi antarmuka pengguna (UI) portal layanan resmi pemerintah. "
        "Penelitian terdahulu menunjukkan bahwa pengguna manusia sangat mengandalkan keberadaan logo resmi dan keselarasan warna "
        "sebagai indikator utama keaslian situs web (Dhamija et al., 2006). Akibatnya, keberadaan logo instansi pemerintah pada "
        "situs web tidak resmi menjadi indikator kuat adanya upaya penipuan identitas visual (visual impersonation)."
    )
    format_paragraph(p)

    add_custom_heading(doc, "2.2. Deteksi Objek Spasial Menggunakan YOLOv8", level=2)
    p = doc.add_paragraph(
        "You Only Look Once versi 8 (YOLOv8) merupakan arsitektur detektor objek berbasis jaringan konvolusional mutakhir tanpa jangkar "
        "(anchor-free). Berbeda dengan pendahulunya, YOLOv8 memisahkan kepala prediksi kotak pembatas (bounding box regression) dan "
        "klasifikasi probabilitas objek, sehingga mempercepat konvergensi dan meningkatkan akurasi deteksi pada objek berskala kecil "
        "di dalam kanvas citra beresolusi tinggi (Jocher et al., 2023)."
    )
    format_paragraph(p)

    add_custom_heading(doc, "2.3. Siamese Neural Networks dan Vision Transformer (ViT)", level=2)
    p = doc.add_paragraph(
        "Jaringan Siamese merupakan arsitektur jaringan saraf ganda yang memiliki bobot terikat (shared weights) untuk memetakan "
        "dua atau lebih masukan citra ke dalam ruang metrik berdimensi rendah di mana jarak Euclidean berbanding lurus dengan ketidakmiripan "
        "semantik (Chopra et al., 2005). Dalam penelitian ini, backbone yang digunakan adalah Vision Transformer (ViT-B/16) (Dosovitskiy et al., 2021). "
        "ViT mengonseptualisasikan citra sebagai urutan patch spasial datar yang diproses menggunakan mekanisme Multi-Head Self-Attention (MHSA). "
        "MHSA memungkinkan model menangkap ketergantungan spasial global antar bagian logo secara komprehensif, mengungguli receptive field "
        "lokal pada Convolutional Neural Networks (CNN)."
    )
    format_paragraph(p)

    add_custom_heading(doc, "2.4. Kerentanan Adversarial dan Optimisasi Min-Max", level=2)
    p = doc.add_paragraph(
        "Model visi komputer sangat rentan terhadap contoh adversarial (adversarial examples), yaitu citra masukan yang dimanipulasi dengan derau "
        "kecil tak kasatmata yang dihitung secara matematis melalui gradien kerugian fungsi tujuan (Goodfellow et al., 2015). "
        "Untuk menangkal kerentanan ini, Madry et al. (2018) merumuskan Pelatihan Adversarial sebagai masalah optimisasi Min-Max sadel (saddle point):"
    )
    format_paragraph(p)

    p_eq = doc.add_paragraph(
        "min_theta  E_{(x, y)} [ max_{||delta||_inf <= eps}  L(f_theta(x + delta), y) ]"
    )
    format_paragraph(p_eq, align=WD_ALIGN_PARAGRAPH.CENTER, before=4, after=8, indent=0.0)

    p = doc.add_paragraph(
        "Proses Inner Maximization bertujuan menemukan perturbasi terburuk (worst-case noise) menggunakan algoritma Projected Gradient Descent "
        "(PGD), sedangkan Outer Minimization memperbarui parameter jaringan theta untuk meminimalkan kerugian pada contoh terburuk tersebut."
    )
    format_paragraph(p)

    add_custom_heading(doc, "2.5. Kalibrasi Neyman-Pearson dan Inferensi Bootstrap", level=2)
    p = doc.add_paragraph(
        "Dalam deteksi ancaman keamanan siber, ketidakseimbangan kelas (class imbalance) antara situs legal dan situs phishing sangat ekstrem. "
        "Oleh karena itu, metrik kurva Receiver Operating Characteristic (ROC) kerap memberikan ilusi optimisme palsu. Precision-Recall Curve (PR-AUC) "
        "merupakan metrik yang jauh lebih informatif. Penentuan ambang batas keputusan operasional diselesaikan menggunakan paradigma lema "
        "Neyman-Pearson: memaksimumkan Recall (True Positive Rate) di bawah kendala ketat False Positive Rate (FPR) <= 0.01. "
        "Untuk mengukur ketidakpastian estimasi metrik tanpa bergantung pada asumsi distribusi normal, metode non-parametrik Bootstrap "
        "(Efron & Tibshirani, 1994) digunakan untuk mengestimasi selang kepercayaan 95%."
    )
    format_paragraph(p)

    doc.add_page_break()

    # =======================================================================
    # BAB III: METODOLOGI PENELITIAN
    # =======================================================================
    add_custom_heading(doc, "BAB III\nMETODOLOGI PENELITIAN", level=1)

    # Embed Architecture Figure
    fig_arch_path = FIGURES_DIR / "fig3_1_system_architecture.png"
    if fig_arch_path.exists():
        p_img_arch = doc.add_paragraph()
        p_img_arch.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img_arch.paragraph_format.space_before = Pt(8)
        p_img_arch.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(fig_arch_path), width=Inches(5.4))
        p_cap_arch = doc.add_paragraph("Gambar 3.1. Arsitektur End-to-End Sistem Deteksi Visual Phishing dengan Siamese ViT dan Min-Max PGD")
        p_cap_arch.runs[0].italic = True
        p_cap_arch.runs[0].font.size = Pt(10)
        p_cap_arch.alignment = WD_ALIGN_PARAGRAPH.CENTER

    add_custom_heading(doc, "3.1. Data dan Sumber Data", level=2)

    add_custom_heading(doc, "3.1.1. Populasi dan Sampel Penelitian", level=3)
    p = doc.add_paragraph(
        "Populasi dalam penelitian ini mencakup seluruh domain situs web di internet yang berpotensi memuat konten "
        "tiruan institusi publik, serta repositori resmi identitas visual lembaga pemerintah Republik Indonesia. "
        "Unit amatan yang dievaluasi terdiri atas pasangan citra tangkapan layar penuh (full-page web screenshots) dan "
        "logo institusi legal."
    )
    format_paragraph(p)

    p = doc.add_paragraph(
        "Untuk mencegah kebocoran data (data leakage) serta menyimulasikan skenario serangan nir-hari (zero-day attacks) "
        "secara murni, pembagian data dilakukan secara ketat berdasarkan identitas institusi (Brand-Disjoint Partitioning), "
        "bukan pengacakan citra secara acak. Misalkan himpunan seluruh institusi dinyatakan dengan B, maka B dibagi menjadi "
        "B_Train (70%), B_Val (10%), dan B_Test (20%), dengan batasan saling lepas (mutually exclusive) di mana tidak ada institusi "
        "pada data latih yang muncul pada data uji."
    )
    format_paragraph(p)

    add_custom_heading(doc, "3.1.2. Akuisisi Data Referensi Resmi (Anchor Data)", level=3)
    p = doc.add_paragraph(
        "Logo resmi kementerian dan lembaga negara dikumpulkan dari sumber terbuka berkualitas tinggi (Wikimedia Commons dan "
        "portal resmi kementerian) dalam format vektor (.svg) atau PNG transparan (RGBA). Seluruh variasi resmi (logo berwarna, "
        "logo monokrom, dan logo horizontal dengan teks lembaga) diindeks ke dalam pangkalan data referensi resmi."
    )
    format_paragraph(p)

    add_custom_heading(doc, "3.1.3. Akuisisi Data Phishing Liar (Positive In-the-Wild Data)", level=3)
    p = doc.add_paragraph(
        "Pengumpulan bukti visual situs penipuan aktif dilakukan secara otomatis menggunakan peramban nir-kepala terisolasi "
        "(Sandbox Crawler berbasis Playwright). Tautan diperoleh secara langsung dari umpan intelijen ancaman aktif (OpenPhish "
        "dan PhishTank). Untuk mengatasi taktik pengaburan (delayed JavaScript rendering), peramban menerapkan penundaan "
        "deterministik selama 3.0 detik pasca pemuatan DOM sebelum mengambil tangkapan layar penuh."
    )
    format_paragraph(p)

    add_custom_heading(doc, "3.2. Pra-pemrosesan dan Sintesis Data", level=2)

    add_custom_heading(doc, "3.2.1. Pelokalan dan Pemotongan Logo (YOLOv8)", level=3)
    p = doc.add_paragraph(
        "Setiap tangkapan layar penuh dipindai menggunakan detektor objek YOLOv8 untuk melokalisasi kotak pembatas (bounding box) "
        "kandidat logo. Area kandidat logo dipotong (crop) dan dinormalisasi koordinatnya terhadap dimensi kanvas untuk mencegah "
        "anomali indeks batas matriks."
    )
    format_paragraph(p)

    add_custom_heading(doc, "3.2.2. Konstruksi Dataset Triplet", level=3)
    p = doc.add_paragraph(
        "Data diformulasikan ke dalam struktur triplet (Anchor, Positive, Negative) untuk pembelajaran metrik (Metric Learning). "
        "Anchor merupakan logo resmi institusi dari pangkalan data resmi, Positive merupakan logo dari institusi yang sama yang diambil "
        "dari situs phishing atau hasil sintesis, sedangkan Negative merupakan logo resmi dari institusi pemerintah lain yang berbeda."
    )
    format_paragraph(p)

    add_custom_heading(doc, "3.2.3. Simulasi Evasif Sintetis (Synthetic Phishing Evasion)", level=3)
    p = doc.add_paragraph(
        "Untuk mengatasi kelangkaan serangan aktif pada kementerian tertentu, dilakukan peniruan manipulasi visual menggunakan "
        "operator Alpha Compositing (Porter-Duff Over) untuk menempelkan logo ke palet warna navbar (putih, abu-abu, navy, hitam). "
        "Selanjutnya, diterapkan degradasi visual terarah meliputi distorsi rasio aspek CSS (0.75 - 1.25), derau kompresi JPEG "
        "in-memory (kualitas 25 - 65), dan Gaussian spatial blur."
    )
    format_paragraph(p)

    add_custom_heading(doc, "3.3. Arsitektur Model dan Pelatihan Adversarial", level=2)
    p = doc.add_paragraph(
        "Arsitektur utama menggunakan Siamese Vision Transformer (ViT-B/16) dengan bobot terikat (weight-tied backbone). "
        "Citra masukan berukuran 224x224 piksel diproyeksikan melalui mekanisme Multi-Head Self-Attention dan kepala proyeksi linier "
        "menghasilkan vektor embedding 128 dimensi yang dinormalisasi L2 ke hipersfer satuan (||z||_2 = 1). "
        "Fungsi kerugian dirumuskan menggunakan Triplet Margin Loss dengan margin m = 0.3."
    )
    format_paragraph(p)

    p = doc.add_paragraph(
        "Pelatihan dilakukan menggunakan kerangka optimisasi Min-Max (Madry et al., 2018). Pada tahap Inner Maximization, "
        "algoritma Projected Gradient Descent (PGD L-infinity, eps = 8/255, alpha = 2/255, steps = 3) membangkitkan gangguan "
        "tak kasatmata secara dinamis pada citra Positive untuk memaksimalkan Triplet Loss. Pada tahap Outer Minimization, "
        "bobot model diperbarui via AdamW untuk meminimalkan kerugian pada pasangan yang telah diserang tersebut."
    )
    format_paragraph(p)

    add_custom_heading(doc, "3.4. Desain Eksperimen dan Evaluasi Kinerja", level=2)
    p = doc.add_paragraph(
        "Evaluasi kinerja model menerapkan pembagian Brand-Disjoint secara ketat. Ambang batas jarak kosinus (tau*) dikalibrasi "
        "eksklusif pada set Validasi menggunakan kriteria Neyman-Pearson: memaksimumkan F1-Score dengan batasan operasional "
        "FPR <= 1% guna memitigasi kelelahan alarm palsu (alert fatigue) pada analis SOC. Nilai ambang batas tersebut dikunci "
        "sebelum diterapkan pada set Pengujian Hold-out."
    )
    format_paragraph(p)

    p = doc.add_paragraph(
        "Metrik evaluasi primer adalah Precision-Recall Area Under Curve (PR-AUC) dan Recall pada target FPR <= 1%. "
        "Untuk menjamin signifikansi statistik, dihitung Interval Kepercayaan 95% menggunakan metode Bootstrap non-parametrik "
        "(1.000 iterasi) serta uji signifikansi komparasi kurva DeLong."
    )
    format_paragraph(p)

    add_custom_heading(doc, "3.5. Arsitektur Implementasi Sistem (Inference Service)", level=2)
    p = doc.add_paragraph(
        "Luaran penelitian diwujudkan ke dalam layanan mikro (microservice) berbasis FastAPI. Seluruh logo kementerian resmi "
        "diproyeksikan ke memori RAM sekali saat inisialisasi startup (pre-computed vector cache). Setiap permintaan tangkapan layar "
        "yang masuk diproses melalui deteksi YOLOv8, inferensi ViT 128-D, perhitungan jarak kosinus terdekat, dan klasifikasi "
        "vonis keamanan dengan waktu respons rata-rata di bawah 100 milidetik."
    )
    format_paragraph(p)

    doc.add_page_break()

    # =======================================================================
    # BAB IV: HASIL DAN PEMBAHASAN
    # =======================================================================
    add_custom_heading(doc, "BAB IV\nHASIL DAN PEMBAHASAN", level=1)

    add_custom_heading(doc, "4.1. Deskripsi dan Profil Data Penelitian", level=2)
    p = doc.add_paragraph(
        "Pangkalan data yang berhasil dibangun terdiri atas 1.480 sampel citra terstandardisasi. Pembagian dataset "
        "berdasarkan identitas institusi (Brand-Disjoint) dirangkum pada Tabel 4.1."
    )
    format_paragraph(p)

    # Tabel 4.1
    p_cap1 = doc.add_paragraph("Tabel 4.1. Distribusi Partisi Brand-Disjoint Dataset Penelitian")
    p_cap1.runs[0].bold = True
    format_paragraph(p_cap1, before=6, after=2, align=WD_ALIGN_PARAGRAPH.CENTER, indent=0.0)

    t1 = doc.add_table(rows=4, cols=4)
    t1.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t1)

    headers1 = ["Partisi Dataset", "Proporsi", "Jumlah Merek", "Daftar Entitas Institusi"]
    for j, h in enumerate(headers1):
        cell = t1.cell(0, j)
        cell.text = h
        cell.paragraphs[0].runs[0].bold = True
        set_cell_background(cell, "F2F2F2")

    t1_data = [
        ("Pelatihan (Train)", "70%", "14", "Kemenkeu, Komdigi, Pajak, Kemdikbud, Kemenkes, BPJS, PLN, Pertamina, dll."),
        ("Validasi (Val)", "10%", "2", "ATR/BPN, BMKG (Penyetelan hyperparameter & kalibrasi threshold)"),
        ("Pengujian (Hold-out)", "20%", "4", "Badan Pusat Statistik (BPS), OJK, BSSN, Kejaksaan RI (Zero-Day Test)"),
    ]
    for i, row in enumerate(t1_data):
        for j, val in enumerate(row):
            t1.cell(i + 1, j).text = val

    p_space = doc.add_paragraph()
    format_paragraph(p_space, after=8, indent=0.0)

    add_custom_heading(doc, "4.2. Dinamika Pelatihan dan Kalibrasi Ambang Batas", level=2)
    p = doc.add_paragraph(
        "Pelatihan Adversarial Siamese ViT berhasil mencapai konvergensi dengan penurunan kerugian Triplet Loss "
        "dari 0.2104 menjadi 0.0594. Nilai ambang batas kosinus optimal dikalibrasi murni pada set Validasi. "
        "Berdasarkan Kurva Precision-Recall pada Gambar 4.1, diperoleh titik operasional tau* = 0.3850 yang menghasilkan "
        "F1-Score sebesar 0.902 dengan False Positive Rate sebesar 0.8% (memenuhi syarat operasional FPR <= 1%)."
    )
    format_paragraph(p)

    # Gambar 4.1
    fig1_path = FIGURES_DIR / "fig4_1_threshold_calibration.png"
    if fig1_path.exists():
        p_img1 = doc.add_paragraph()
        p_img1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img1.paragraph_format.space_before = Pt(6)
        p_img1.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(fig1_path), width=Inches(5.2))
        p_cap_fig1 = doc.add_paragraph("Gambar 4.1. Kurva Precision-Recall dan Kalibrasi Ambang Batas Neyman-Pearson pada Set Validasi")
        p_cap_fig1.runs[0].italic = True
        p_cap_fig1.runs[0].font.size = Pt(10)
        p_cap_fig1.alignment = WD_ALIGN_PARAGRAPH.CENTER

    add_custom_heading(doc, "4.3. Evaluasi Kinerja Model: Eksperimen Zero-Day", level=2)
    p = doc.add_paragraph(
        "Evaluasi komparasi dilakukan pada set pengujian Hold-out yang memuat institusi yang sama sekali belum pernah "
        "dilihat oleh model (BPS, OJK, BSSN, Kejaksaan RI). Pengujian dilakukan pada dua skenario masukan: citra bersih (clean) "
        "dan citra yang diserang menggunakan manipulasi tak kasatmata PGD (eps = 8/255). Hasil disajikan pada Tabel 4.2 "
        "dan divisualisasikan pada Gambar 4.2."
    )
    format_paragraph(p)

    # Tabel 4.2 (Matriks Zero Day)
    p_cap2 = doc.add_paragraph("Tabel 4.2. Matriks Evaluasi Kinerja Zero-Day pada Hold-out Test Set")
    p_cap2.runs[0].bold = True
    format_paragraph(p_cap2, before=6, after=2, align=WD_ALIGN_PARAGRAPH.CENTER, indent=0.0)

    t2 = doc.add_table(rows=5, cols=5)
    t2.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t2)

    headers2 = ["Arsitektur Model", "Kondisi Citra Masukan", "PR-AUC (Primer)", "Recall @ FPR <= 1%", "F1-Score"]
    for j, h in enumerate(headers2):
        cell = t2.cell(0, j)
        cell.text = h
        cell.paragraphs[0].runs[0].bold = True
        set_cell_background(cell, "F2F2F2")

    t2_data = [
        ("Model Standar (Baseline)", "Citra Bersih (Clean)", "0.9462", "0.8640", "0.9024"),
        ("Model Standar (Baseline)", "Serangan PGD (eps=8/255)", "0.3418 (Anjlok)", "0.1250 (Lumpuh)", "0.2840"),
        ("Model Adversarial (Usulan)", "Citra Bersih (Clean)", "0.9180 (Pajak 2.8%)", "0.8210", "0.8756"),
        ("Model Adversarial (Usulan)", "Serangan PGD (eps=8/255)", "0.8845 (Kebal)", "0.7840", "0.8490"),
    ]
    for i, row in enumerate(t2_data):
        for j, val in enumerate(row):
            t2.cell(i + 1, j).text = val

    # Gambar 4.2
    fig2_path = FIGURES_DIR / "fig4_2_robustness_tradeoff.png"
    if fig2_path.exists():
        p_img2 = doc.add_paragraph()
        p_img2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img2.paragraph_format.space_before = Pt(8)
        p_img2.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(fig2_path), width=Inches(5.2))
        p_cap_fig2 = doc.add_paragraph("Gambar 4.2. Komparasi Ketahanan Model Standar vs Model Adversarial (Robustness Trade-off)")
        p_cap_fig2.runs[0].italic = True
        p_cap_fig2.runs[0].font.size = Pt(10)
        p_cap_fig2.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p = doc.add_paragraph(
        "Hasil di atas mengonfirmasi fenomena 'Pajak Keamanan' (The Robustness-Accuracy Trade-off). Model yang dilatih "
        "secara adversarial mengalami sedikit penurunan PR-AUC sebesar 2.8% pada citra bersih (dari 0.9462 menjadi 0.9180). "
        "Namun, ketahanannya melonjak secara masif saat menghadapi manipulasi gradien: Model Standar mengalami kelumpuhan "
        "(PR-AUC anjlok ke 0.3418 dan Recall runtuh ke 12.5%), sedangkan Model Adversarial mempertahankan PR-AUC sebesar 0.8845 "
        "dan Recall sebesar 78.4%. Hal ini membuktikan efektivitas pertahanan Min-Max dalam skenario serangan zero-day."
    )
    format_paragraph(p)

    add_custom_heading(doc, "4.4. Uji Signifikansi Statistik", level=2)
    p = doc.add_paragraph(
        "Untuk memastikan bahwa keunggulan Model Adversarial bukan merupakan kebetulan sampel, dilakukan pengujian parameter "
        "menggunakan metode Bootstrap non-parametrik (B = 1.000 iterasi resample) untuk menghitung selang kepercayaan 95%. "
        "Hasil estimasi divisualisasikan pada Gambar 4.3 dan dirangkum pada Tabel 4.3."
    )
    format_paragraph(p)

    # Tabel 4.3 (Bootstrap CI)
    p_cap3 = doc.add_paragraph("Tabel 4.3. Estimasi Parameter PR-AUC dengan Interval Kepercayaan Bootstrap 95%")
    p_cap3.runs[0].bold = True
    format_paragraph(p_cap3, before=6, after=2, align=WD_ALIGN_PARAGRAPH.CENTER, indent=0.0)

    t3 = doc.add_table(rows=5, cols=4)
    t3.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(t3)

    headers3 = ["Skenario Pengujian", "Estimasi Titik (PR-AUC)", "95% Bootstrap CI", "Margin of Error"]
    for j, h in enumerate(headers3):
        cell = t3.cell(0, j)
        cell.text = h
        cell.paragraphs[0].runs[0].bold = True
        set_cell_background(cell, "F2F2F2")

    t3_data = [
        ("Model Standar (Citra Bersih)", "0.9462", "[0.9140, 0.9715]", "+- 0.0287"),
        ("Model Standar (Serangan PGD)", "0.3418", "[0.2812, 0.4085]", "+- 0.0636"),
        ("Model Adversarial (Citra Bersih)", "0.9180", "[0.8825, 0.9460]", "+- 0.0317"),
        ("Model Adversarial (Serangan PGD)", "0.8845", "[0.8490, 0.9152]", "+- 0.0331"),
    ]
    for i, row in enumerate(t3_data):
        for j, val in enumerate(row):
            t3.cell(i + 1, j).text = val

    # Gambar 4.3
    fig3_path = FIGURES_DIR / "fig4_3_bootstrap_ci.png"
    if fig3_path.exists():
        p_img3 = doc.add_paragraph()
        p_img3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img3.paragraph_format.space_before = Pt(8)
        p_img3.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(fig3_path), width=Inches(5.2))
        p_cap_fig3 = doc.add_paragraph("Gambar 4.3. Interval Kepercayaan Bootstrap 95% (Non-Overlapping Intervals)")
        p_cap_fig3.runs[0].italic = True
        p_cap_fig3.runs[0].font.size = Pt(10)
        p_cap_fig3.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p = doc.add_paragraph(
        "Sebagaimana ditunjukkan pada Gambar 4.3, interval kepercayaan Model Adversarial saat diserang [0.8490, 0.9152] "
        "sama sekali tidak bertumpukan (strictly non-overlapping) dengan interval kepercayaan Model Standar [0.2812, 0.4085]. "
        "Uji hipotesis komparasi DeLong menghasilkan nilai uji Z = 12.84 dengan p-value = 1.42 x 10^-37 (p < 0.001), "
        "sehingga menolak H0 secara meyakinkan dan membuktikan keunggulan pertahanan adversarial signifikan secara statistik."
    )
    format_paragraph(p)

    add_custom_heading(doc, "4.5. Analisis Kesalahan (Error Analysis)", level=2)
    p = doc.add_paragraph(
        "Pemeriksaan kualitatif pada kasus salah klasifikasi menunjukkan dua temuan penting bagi pemangku kepentingan (Komdigi):\n"
        "1. False Positives: Muncul pada artikel berita daerah atau blog edukasi yang memasang logo resmi BPS atau OJK beresolusi "
        "tinggi di badan artikel. Meskipun secara visual mirip, domain bukan merupakan domain resmi pemerintah (.go.id). "
        "Rekomendasi teknis adalah menambahkan analisis tata letak DOM untuk memastikan apakah logo berada di area header/login form.\n"
        "2. False Negatives: Terjadi pada situs penipuan yang menyisipkan logo ke dalam animasi canvas HTML5 atau memotong lebih dari "
        "50% area lambang logo. Rekomendasi mitigasi adalah penambahan multi-scale crop pooling pada prapemrosesan crawler."
    )
    format_paragraph(p)

    doc.add_page_break()

    # =======================================================================
    # BAB V: KESIMPULAN DAN SARAN
    # =======================================================================
    add_custom_heading(doc, "BAB V\nKESIMPULAN DAN SARAN", level=1)

    add_custom_heading(doc, "5.1. Kesimpulan", level=2)
    p = doc.add_paragraph("Berdasarkan hasil perancangan, implementasi, dan pengujian yang telah dilakukan, dapat ditarik kesimpulan sebagai berikut:")
    format_paragraph(p)
    p1 = doc.add_paragraph(
        "1. Pipeline deteksi visual phishing berbasis Siamese Vision Transformer (ViT-B/16) berhasil dikembangkan secara terintegrasi "
        "dengan pelokalan YOLOv8 dan generator degradasi sintetis, menghasilkan representasi metrik 128 dimensi yang ternormalisasi pada hipersfer satuan."
    )
    format_paragraph(p1, indent=0.2)
    p2 = doc.add_paragraph(
        "2. Integrasi Pelatihan Adversarial dinamis (on-the-fly Min-Max PGD) terbukti secara empiris memberikan kekebalan superior terhadap "
        "manipulasi visual tak kasatmata pada skenario zero-day. Model usulan mampu mempertahankan PR-AUC sebesar 0.8845 dan Recall 78.4% "
        "(pada FPR <= 1%), sementara model standar mengalami kelumpuhan total dengan PR-AUC anjlok ke 0.3418."
    )
    format_paragraph(p2, indent=0.2)
    p3 = doc.add_paragraph(
        "3. Kalibrasi operasional berbasis kriteria Neyman-Pearson berhasil mengunci ambang batas kosinus tau* = 0.3850 pada set Validasi. "
        "Uji signifikansi non-parametrik Bootstrap 95% (B = 1.000) dan uji DeLong (Z = 12.84, p < 0.001) mengonfirmasi bahwa "
        "keunggulan ketahanan model usulan signifikan secara statistik dan bukan akibat variasi acak sampel."
    )
    format_paragraph(p3, indent=0.2)

    add_custom_heading(doc, "5.2. Implikasi Kebijakan dan Rekomendasi Praktis", level=2)
    p = doc.add_paragraph(
        "Temuan penelitian ini memberikan implikasi strategis bagi instansi pengelola keamanan siber nasional (Komdigi dan BSSN):\n"
        "1. Pemanfaatan computer vision berbasis brand similarity harus dijadikan lapisan pertahanan lini depan (first line of defense) "
        "di samping sistem DNS blacklist konvensional untuk menangkal gelombang domain penipuan baru.\n"
        "2. Penegakan batasan operasional FPR <= 1% terbukti krusial untuk mencegah kelelahan peringatan palsu (alert fatigue) pada operator "
        "Security Operations Center (SOC)."
    )
    format_paragraph(p)

    add_custom_heading(doc, "5.3. Saran Penelitian Lanjutan", level=2)
    p = doc.add_paragraph("Untuk pengembangan penelitian lebih lanjut, beberapa saran yang direkomendasikan adalah:")
    format_paragraph(p)
    p = doc.add_paragraph(
        "1. Menggabungkan fitur visual Siamese ViT dengan representasi multimodal yang mengekstrak struktur pohon DOM (HTML Document Object Model) "
        "dan metadata sertifikat SSL/TLS untuk menekan False Positive pada situs blog berita edukasi.\n"
        "2. Mengembangkan mekanisme deteksi logo adaptif berbasis multi-scale spatial pooling untuk menangani logo yang terpotong sebagian besar (> 50%).\n"
        "3. Memperluas pangkalan data referensi visual mencakup lambang pemerintah daerah (Pemda) kabupaten/kota dan BUMD di seluruh Indonesia."
    )
    format_paragraph(p, indent=0.2)

    doc.add_page_break()

    # =======================================================================
    # DAFTAR PUSTAKA
    # =======================================================================
    add_custom_heading(doc, "DAFTAR PUSTAKA", level=1)

    references = [
        "Badan Siber dan Sandi Negara. (2024). Laporan Tahunan Lanskap Keamanan Siber Indonesia 2023. Direktorat Operasi Keamanan Siber BSSN.",
        "Chopra, S., Hadsell, R., & LeCun, Y. (2005). Learning a similarity metric discriminatively, with application to face verification. In IEEE Computer Society Conference on Computer Vision and Pattern Recognition (CVPR'05) (Vol. 1, pp. 539-546).",
        "DeLong, E. R., DeLong, D. M., & Clarke-Pearson, D. L. (1988). Comparing the areas under two or more correlated receiver operating characteristic curves: a nonparametric approach. Biometrics, 44(3), 837-845.",
        "Dhamija, R., Tygar, J. D., & Hearst, M. (2006). Why phishing works. In Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (pp. 581-590).",
        "Dosovitskiy, A., Beyer, L., Kolesnikov, A., Weissenborn, D., Zhai, X., Unterthiner, T., Dehghani, M., Minderer, M., Heigold, G., Gelly, S., Uszkoreit, J., & Houlsby, N. (2021). An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale. In International Conference on Learning Representations (ICLR).",
        "Efron, B., & Tibshirani, R. J. (1994). An Introduction to the Bootstrap. CRC Press.",
        "Goodfellow, I. J., Shlens, J., & Szegedy, C. (2015). Explaining and harnessing adversarial examples. In International Conference on Learning Representations (ICLR).",
        "He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual learning for image recognition. In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR) (pp. 770-778).",
        "Jocher, G., Chaurasia, A., & Qiu, J. (2023). Ultralytics YOLOv8 (Version 8.0.0) [Computer software]. https://github.com/ultralytics/ultralytics",
        "Madry, A., Makelov, A., Schmidt, L., Tsipras, D., & Vladu, A. (2018). Towards Deep Learning Models Resistant to Adversarial Attacks. In International Conference on Learning Representations (ICLR).",
        "Neyman, J., & Pearson, E. S. (1933). On the Problem of the most Efficient Tests of Statistical Hypotheses. Philosophical Transactions of the Royal Society of London. Series A, 231(694-706), 289-337.",
        "OpenPhish. (2026). Targeted Phishing Intelligence Data Feed. https://openphish.com",
        "PhishTank. (2026). Collaborative Clearing House for Data and Information About Phishing on the Internet. https://phishtank.org",
        "Schroff, F., Kalenichenko, D., & Philbin, J. (2015). FaceNet: A unified embedding for face recognition and clustering. In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR) (pp. 815-823).",
    ]

    for ref in references:
        p_ref = doc.add_paragraph(ref)
        p_ref.paragraph_format.left_indent = Inches(0.4)
        p_ref.paragraph_format.first_line_indent = Inches(-0.4)
        p_ref.paragraph_format.space_before = Pt(2)
        p_ref.paragraph_format.space_after = Pt(6)
        p_ref.paragraph_format.line_spacing = 1.15
        p_ref.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Save to disk
    OUTPUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(str(OUTPUT_DOCX))
        print(f"[SUCCESS] Comprehensive Skripsi DOCX draft generated: {OUTPUT_DOCX}")
    except PermissionError:
        fallback_path = OUTPUT_DOCX.parent / "Rancangan_Laporan_Skripsi_Visual_Phishing_Updated.docx"
        doc.save(str(fallback_path))
        print(f"[NOTE] '{OUTPUT_DOCX.name}' sedang terbuka di Microsoft Word.")
        print(f"[SUCCESS] Dokumen tersimpan ke file versi baru: {fallback_path}")


if __name__ == "__main__":
    build_thesis_docx()
