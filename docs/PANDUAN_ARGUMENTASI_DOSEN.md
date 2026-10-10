# PANDUAN NGOBROL & ARGUMENTASI DENGAN DOSEN
## Skripsi: Deteksi Visual Phishing dengan Siamese Vision Transformer & Adversarial Training

Panduan ini ditulis dengan **bahasa tutur yang alami dan luwes**—seperti cara mahasiswa cerdas berbicara santai tapi berbobot saat bimbingan atau ujian sidang di STIS. Tidak kaku, tidak hafalan robot, tapi tetap sopan dan nancep di substansi.

---

## 1. Cara Menjelaskan Inti Skripsi dalam 2 Menit (Elevator Pitch)

> **Situasi:** Dosen menyandarkan punggung, lalu bilang:  
> *"Coba ceritakan santai aja, skripsi kamu ini sebenarnya mau ngapain dan kenapa ini penting?"*

### 🎙️ Cara Menjawab yang Enak Didengar:
> *"Jadi begini Pak/Bu, masalah utamanya sebenarnya sederhana tapi dampaknya fatal.*
>
> *Masyarakat kita itu rata-rata nggak merhatiin nama domain di browser. Mau link-nya berakhiran `.go.id`, `.xyz`, atau `.pages.dev`, kebanyakan orang nggak paham bedanya. Tapi ada satu hal yang bikin mereka langsung percaya: **begitu mereka buka halaman web dan melihat ada Logo Garuda, Logo Ditjen Pajak, atau Logo BPS**, rasa curiganya langsung hilang. Mereka mikir, 'Oh, ini situs resmi pemerintah,' lalu dengan gampang masukin NIK, password, sampai nomor rekening.*
>
> *Di sisi lain, cara lama Kominfo memblokir web penipuan lewat sistem blacklist itu punya jeda 1 sampai 3 hari karena nunggu laporan manual. Padahal web phishing zaman sekarang umurnya cuma 2 sampai 4 jam sebelum dibuang oleh pelaku.*
>
> *Nah, satu-satunya hal yang nggak bisa dihindari oleh penyerang adalah: **mereka wajib pasang logo instansi** biar korbannya percaya.*
>
> *Di skripsi ini, saya bikin sistem AI penglihatan (Vision Transformer) yang tugasnya mencocokkan kemiripan logo kementerian secara otomatis. Bedanya dengan penelitian luar negeri:*
> 1. *Model saya dilatih tahan banting melawan manipulasi derau tak kasatmata (adversarial attack), jadi nggak gampang dikelabui penyerang.*
> 2. *Diuji murni pada skenario instansi yang belum pernah dipelajari model sebelumnya (zero-day).*
> 3. *Dan yang paling penting dari sisi statistika STIS: ambang batas keputusannya diuji ketat pakai kriteria Neyman-Pearson dan signifikansinya dibuktikan lewat Bootstrap 1.000 kali putaran.*
>
> *Output-nya sudah jadi API siap pakai dengan kecepatan respons di bawah 100 milidetik, jadi realistis buat dipakai BSSN atau Komdigi. Kurang lebih seperti itu intinya, Pak/Bu."*

---

## 2. Kalau Dosen Meragukan: "Emang Ada Korbannya? Bukannya Phishing Cuma APK di WhatsApp?"

### 🎙️ Cara Menjawab Santai tapi Menusuk Fakta:
> *"Betul Pak/Bu, sekarang memang banyak yang kirim undangan APK lewat WA. Tapi kalau kita bedah alurnya, pesan WA itu cuma pintunya saja.*
>
> *Begitu link-nya diklik, korban tetap dilempar ke halaman web peramban. Nah, di halaman web itulah penipuan visualnya bekerja.*
>
> *Apalagi sekarang pelaku nggak perlu sewa server mahal-mahal. Mereka pakai layanan cloud gratisan kayak Cloudflare Pages atau Firebase yang otomatis dapet HTTPS gembok hijau. Orang awam kalau lihat ada gembok hijau dan ada logo kementerian, mereka langsung ngerasa aman.*
>
> *Kasusnya nyata banget di lapangan, Pak/Bu:*
> * *Di Pajak, banyak wajib pajak ketipu situs e-Filing palsu berkedok pengembalian lebih bayar.*
> * *Di Kemensos, ribuan NIK warga dicuri lewat web tiruan 'Cek Bansos' buat dipakai pinjol ilegal.*
> * *Di BPS sendiri, sering ada web tiruan rekrutmen mitra statistik yang mungut biaya pendaftaran.*
> * *Dan di OJK, logo mereka dicatut di web investasi bodong biar kelihatan resmi.*
>
> *Jadi ancamannya bukan cuma orang kehilangan uang, tapi kepercayaan publik ke layanan digital pemerintah yang ikut rusak."*

---

## 3. Kalau Dosen Nanya Kebaruan: "Di Luar Negeri Kan Sudah Banyak Riset Begini (Kayak Phishpedia)?"

### 🎙️ Cara Menjawab Jujur dan Berkelas:
> *"Betul sekali Pak/Bu, paper luar seperti Phishpedia di USENIX memang jadi kiblat awal.*
>
> *Tapi setelah saya bedah paper mereka, ada satu kelemahan besar: **mereka menganggap penyerangnya pasif dan polos**. Model mereka cuma dites pakai logo bersih hasil cropping biasa.*
>
> *Padahal di dunia nyata, penyerang yang pintar bisa ngasih sedikit derau piksel halus—namanya serangan PGD. Di mata manusia logonya tetap kelihatan normal kayak logo BPS, tapi AI luar negeri itu langsung 'buta' dan akurasinya anjlok parah ke belasan persen.*
>
> *Nah, celah itulah yang saya selesaikan di skripsi ini:*
> 1. *Model saya nggak dilatih secara pasif, tapi pakai konsep Min-Max Game Theory. Jadi pas latihan, model dipaksa bertarung melawan serangan derau PGD biar kebal.*
> 2. *Arsitekturnya saya naikkan dari CNN biasa ke Vision Transformer (ViT-B/16), jadi AI-nya melihat logo secara menyeluruh, bukan cuma tekstur lokal.*
> 3. *Dan dataset luar negeri itu isinya logo minimalis kayak Apple atau Netflix. Belum ada yang meneliti logo instansi Indonesia yang penuh ornamen lambang heraldik rumit kayak Garuda, padi-kapas, dan lingkaran teks.*
>
> *Jadi kita nggak bikin ulang dari nol, tapi memperbaiki kelemahan fatal dari riset dunia yang sudah ada."*

---

## 4. Kalau Dosen Nanya Sisi STIS: "Ini Kayak Skripsi Informatika, Mana Statistikanya?"

> *(PENTING: Ini pertanyaan paling menentukan nilai Anda di STIS. Jawab dengan tenang dan tunjukkan ketajaman statistikanya).*

### 🎙️ Cara Menjawab dengan Karakter Anak Komputasi Statistik:
> *"Justru di bagian evaluasinya ini 'jiwa STIS'-nya keluar penuh, Pak/Bu.*
>
> *Kalau teman-teman di Informatika biasanya puas cuma dengan pamer angka deskriptif satu titik—misal akurasinya 92%, terus selesai. Nah, di skripsi ini saya perlakukan hasil AI itu sebagai penduga statistik yang punya ketidakpastian.*
>
> *Ada tiga hal statistik murni yang saya terapkan:*
> 1. **Optimisasi Bersyarat Neyman-Pearson:**  
>    *Threshold atau ambang batas vonisnya nggak saya tebak-tebak pakai angka 0.5. Saya kalibrasi pakai Lema Neyman-Pearson: kita maksimalkan Recall, tapi kita kunci False Positive Rate-nya maksimal 1%. Kenapa 1%? Karena kalau sistem keamanan sering salah tuduh, analis di BSSN bakal kena 'alert fatigue' atau capek ngurusin alarm palsu.*
> 2. **Inferensi Non-Parametrik Bootstrap 1.000 Kali:**  
>    *Saya nggak mau mengasumsikan datanya berdistribusi normal. Jadi saya lakukan resampling Bootstrap 1.000 kali buat nyari Selang Kepercayaan 95% dari metrik PR-AUC. Hasilnya terbukti selang kepercayaan model usulan saya sama sekali nggak tumpang tindih dengan model baseline.*
> 3. **Uji Hipotesis Komparasi DeLong:**  
>    *Saya lakukan uji hipotesis formal pakai uji DeLong buat ngebuktiin apakah selisih performa model saya ini beneran beda nyata secara statistik atau cuma kebetulan sampel lagi bagus. Nilai p-value-nya jauh di bawah 0.001, jadi penolakan H0-nya sangat meyakinkan.*
>
> *Jadi metodologi pengujian di skripsi ini murni inferensi statistika, bukan sekadar coba-coba coding."*

---

## 5. Kalau Dosen Nanya: "Kenapa Pembagian Datanya Harus Brand-Disjoint? Kenapa Nggak Diacak Biasa?"

### 🎙️ Cara Menjawab yang Menunjukkan Pemahaman Metodologis:
> *"Kalau kita acak gambarnya kayak split biasa di machine learning, nanti logo Kemenkeu yang asli ada di data latih, terus logo Kemenkeu yang tiruan ada di data uji.*
>
> *Itu namanya **kebocoran data (Data Leakage)**, Pak/Bu. Modelnya bakal kelihatan pintar banget dapat skor 99%, padahal aslinya dia cuma menghafal bentuk logo yang sudah pernah dia lihat.*
>
> *Di lapangan, serangan yang paling berbahaya itu serangan Zero-Day: tiba-tiba ada web penipu bikin tiruan instansi yang model AI-nya belum pernah lihat sama sekali pas latihan—misalnya BPS atau OJK.*
>
> *Makanya saya pakai metode **Brand-Disjoint**: instansi yang dipakai buat ujian akhir (BPS, OJK, BSSN, Kejaksaan) bener-bener diisolasi total. Model nggak boleh ngintip logo itu sepeser pun selama masa pelatihan. Dengan begitu, hasil pengujiannya jujur dan mencerminkan kondisi lapangan yang sebenarnya."*

---

## 6. Kalau Dosen Nanya: "Nanti Kalau Sudah Lulus, Siapa yang Mau Pakai Ini?"

### 🎙️ Cara Menjawab yang Realistis dan Membumi:
> *"Target penerima manfaatnya sangat konkret, Pak/Bu:*
>
> * *Pertama, buat **BSSN (Gov-CSIRT)**. Sistem ini bisa dipasang di bot crawling mereka buat menyisir domain-domain baru yang muncul tiap hari. Kalau ada web aneh yang masang logo kementerian, sistem langsung ngasih peringatan dini sebelum jatuh korban.*
> * *Kedua, buat **Komdigi (AduanKonten)**, buat memotong verifikasi manual laporan aduan masyarakat yang biasanya makan waktu berhari-hari.*
> * *Dan ketiga, tentu buat **CSIRT BPS** sendiri untuk memproteksi portal sensus, survei, dan rekrutmen mitra dari web tiruan.*
>
> *Dan sistem ini bukan cuma konsep di atas kertas atau notebook. Saya sudah bungkus kodenya jadi API microservice pakai FastAPI dengan kecepatan respons di bawah 100 milidetik, jadi memang sudah siap diintegrasikan ke sistem nyata."*

---

## 7. Cheatsheet Mental: Kata-Kata Pengganti Istilah Kaku

Biar gaya bicaramu mengalir luwes dan tidak terdengar seperti membaca teks:

| Jangan Pakai Kalimat Kaku Ini (Terlalu Robot) ❌ | Pakai Bahasa Alami Ini Saja (Luwes & Nancep) ✅ |
| :--- | :--- |
| *"Izin menjawab, penelitian ini dilatarbelakangi oleh paradoks kritis..."* | *"Jadi begini Pak/Bu, masalah utamanya sebenarnya sederhana tapi dampaknya bahaya..."* |
| *"Mekanisme pertahanan tradisional mengalami fenomena detection lag..."* | *"Cara lama Kominfo itu punya jeda 1 sampai 3 hari karena nunggu laporan manual..."* |
| *"Model saya mengintegrasikan formulasi optimisasi minimax madry..."* | *"Model saya dilatih pakai konsep game theory, jadi pas latihan AI-nya dipaksa bertarung melawan serangan derau biar kebal..."* |
| *"Kami memitigasi anomali data leakage melalui brand-disjoint partitioning..."* | *"Datanya sengaja kita pisah berdasarkan instansi, biar modelnya nggak cuma menghafal logo yang sudah pernah dilihat..."* |
| *"Untuk membuktikan signifikansi empiris non-parametrik..."* | *"Biar nggak cuma klaim angka akurasi doang, saya uji pakai Bootstrap 1.000 kali buat ngebuktiin selisihnya beneran nyata..."* |

---

> **Pesan Penutup:**  
> Dosen itu paling suka melihat mahasiswa yang **paham apa yang dia kerjakan dan bisa menjelaskannya dengan bahasa manusia yang jernih**. Kuasai alur ceritanya, jawab dengan santai tapi tegas pada konsep matematisnya, Anda pasti sukses besar di sidang!
