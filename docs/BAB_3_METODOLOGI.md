# BAB 3: METODOLOGI PENELITIAN

## 3.1. Data dan Sumber Data

### 3.1.1. Populasi dan Sampel Penelitian
Populasi dalam penelitian ini mencakup seluruh domain situs web di internet yang berpotensi memuat konten tiruan institusi publik, serta repositori resmi identitas visual lembaga pemerintah Republik Indonesia. Unit amatan yang dievaluasi terdiri atas pasangan citra tangkapan layar penuh (*full-page web screenshots*) dan logo institusi legal.

Untuk mencegah kebocoran data (*data leakage*) serta menyimulasikan skenario serangan nir-hari (*zero-day attacks*), pembagian data dilakukan secara ketat berdasarkan identitas institusi (**Brand-Disjoint Partitioning**), bukan pengacakan citra (*image-level shuffling*). Misalkan $\mathcal{B}$ adalah himpunan seluruh entitas kementerian/lembaga:
$$\mathcal{B} = \mathcal{B}_{\text{Train}} \cup \mathcal{B}_{\text{Val}} \cup \mathcal{B}_{\text{Test}}$$
dengan batasan disjoin mutually exclusive:
$$\mathcal{B}_{\text{Train}} \cap \mathcal{B}_{\text{Val}} = \emptyset, \quad \mathcal{B}_{\text{Train}} \cap \mathcal{B}_{\text{Test}} = \emptyset, \quad \mathcal{B}_{\text{Val}} \cap \mathcal{B}_{\text{Test}} = \emptyset$$

* **Set Pelatihan ($\mathcal{B}_{\text{Train}}$ - 70%):** Model mempelajari representasi invariansi visual umum dan batas metrik spasial.
* **Set Validasi ($\mathcal{B}_{\text{Val}}$ - 10%):** Digunakan murni untuk pencarian *hyperparameter* dan penguncian ambang batas operasional ($\tau$).
* **Set Pengujian Hold-out ($\mathcal{B}_{\text{Test}}$ - 20%):** Institusi yang sama sekali belum pernah dilihat oleh model selama proses pelatihan untuk mengukur daya generalisasi *zero-day*.

### 3.1.2. Akuisisi Data Referensi Resmi (*Anchor Data*)
Data logo resmi kementerian dan lembaga negara dikumpulkan dari sumber terbuka berkualitas tinggi (Wikimedia Commons dan repositori resmi instansi) dalam format vektor (`.svg`) atau PNG resolusi tinggi dengan kanal transparansi (*RGBA*). Seluruh variasi resmi (logo berwarna, monokrom, dan logo horizontal dengan teks lembaga) diindeks ke dalam pangkalan data referensi:
$$\mathcal{D}_{\text{ref}} = \{(x_{\text{ref}}^{(i)}, b_i) \mid b_i \in \mathcal{B}\}$$

### 3.1.3. Akuisisi Data Phishing Liar (*Positive In-the-Wild Data*)
Pengumpulan bukti visual situs penipuan aktif dilakukan secara otomatis menggunakan peramban nir-kepala terisolasi (*Sandbox Crawler* berbasis Playwright). Tautan diperoleh secara langsung dari umpan intelijen ancaman (*live threat intelligence feeds*) publik OpenPhish dan PhishTank.

Untuk mengatasi taktik pengaburan (*evasion*) seperti *delayed JavaScript rendering*, peramban menerapkan penundaan deterministik $t_{\text{render}} = 3.0$ detik pasca *DOMContentLoaded* sebelum mengambil tangkapan layar penuh:
$$I_{\text{screenshot}} \in \mathbb{R}^{H \times W \times 3}$$

---

## 3.2. Pra-pemrosesan dan Sintesis Data

### 3.2.1. Pelokalan dan Pemotongan Logo (YOLOv8)
Setiap tangkapan layar penuh dipindai menggunakan detektor objek YOLOv8 untuk melokalisasi kotak pembatas kandidat logo $\mathbf{b} = [x_1, y_1, x_2, y_2]$:
$$\hat{\mathbf{b}} = \arg\max_{\mathbf{b}} \text{Confidence}(\mathbf{b})$$
Citra dipotong (*cropped*) dan dinormalisasi koordinatnya terhadap batas kanvas citra untuk mencegah indeks di luar batas (*out-of-bounds indexing*).

### 3.2.2. Konstruksi Dataset Triplet
Data diformulasikan ke dalam struktur triplet $(\mathbf{x}_a, \mathbf{x}_p, \mathbf{x}_n)$ untuk pembelajaran metrik (*Metric Learning*):
* $\mathbf{x}_a$ (*Anchor*): Logo resmi institusi $b \in \mathcal{B}$ dari $\mathcal{D}_{\text{ref}}$.
* $\mathbf{x}_p$ (*Positive*): Potongan logo institusi yang sama $b$ dari situs *phishing* atau hasil sintesis.
* $\mathbf{x}_n$ (*Negative*): Logo resmi institusi lain $b' \in \mathcal{B}$, di mana $b' \neq b$.

### 3.2.3. Simulasi Evasif Sintetis (*Synthetic Phishing Evasion*)
Untuk mengatasi kelangkaan serangan aktif pada kementerian tertentu, dilakukan peniruan degradasi visual menggunakan operator komposisi *Porter-Duff Over*:
$$I_{\text{out}}(u, v) = \alpha(u, v) \cdot I_{\text{logo}}(u, v) + \big(1 - \alpha(u, v)\big) \cdot I_{\text{bg}}(u, v)$$
di mana $\alpha(u, v) \in [0, 1]$ adalah nilai kanal alfa ternormalisasi, dan $I_{\text{bg}}$ adalah kanvas latar warna *header* situs web ($\text{Putih}, \text{Abu-abu}, \text{Navy}, \text{Hitam}$). 

Selanjutnya diterapkan degradasi visual terukur:
1. **Warping Rasio Aspek:** Penskalaan non-proporsional $s_x, s_y \sim \mathcal{U}(0.75, 1.25)$ untuk menyimulasikan kelalaian penataan CSS.
2. **Kuantisasi DCT JPEG:** Kompresi lossy dalam memori dengan faktor kualitas $Q \sim \mathcal{U}(25, 65)$.
3. **Filter Spasial Gaussian:** Konvolusi konvensional $I * G_\sigma$ untuk menyimulasikan tangkapan beresolusi rendah.

---

## 3.3. Arsitektur Model dan Pelatihan Adversarial

```
                ┌────────────────────────────────────────────────────────┐
                │             SIAMESE VISION TRANSFORMER                 │
                └────────────────────────────────────────────────────────┘
  Anchor (A)   ──►[ Shared ViT-B/16 ]──►[ Projection Head ]──► ||z_a||_2 = 1 ──┐
                                                                               ├─► Triplet Margin Loss
  Positive (P) ──►[ + PGD Noise ] ──►[ Shared ViT-B/16 ]──► ||z_p_adv||_2 = 1 ─┤   L(z_a, z_p_adv, z_n)
                                                                               │
  Negative (N) ──►[ Shared ViT-B/16 ]──►[ Projection Head ]──► ||z_n||_2 = 1 ──┘
```

### 3.3.1. Siamese Vision Transformer (ViT-B/16)
Arsitektur menggunakan Vision Transformer (*ViT-B/16*) sebagai *backbone* ekstraksi fitur bersama (*weight-tied backbone*). Citra masukan $x \in \mathbb{R}^{224 \times 224 \times 3}$ dipecah menjadi $N = 196$ *patch* berukuran $16 \times 16$:
$$z_0 = [x_{\text{class}}; x_p^1 \mathbf{E}; x_p^2 \mathbf{E}; \dots; x_p^N \mathbf{E}] + \mathbf{E}_{\text{pos}}$$
di mana representasi fitur spasial diekstraksi melalui multi-head self-attention:
$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$
Lapisan klasifikasi diganti dengan kepala proyeksi metrik:
$$z = \text{Linear}_{384 \to 128}\left(\text{Dropout}\left(\text{GELU}\left(\text{Linear}_{768 \to 384}(h_{\text{cls}})\right)\right)\right)$$
Vektor akhir diproyeksikan ke hipersfer satuan melalui normalisasi $L_2$:
$$\hat{z} = \frac{z}{\|z\|_2}$$

### 3.3.2. Fungsi Kerugian Pembelajaran Metrik (*Triplet Margin Loss*)
Pada hipersfer satuan, kuadrat jarak Euclidean ekuivalen secara linier dengan jarak kosinus:
$$\|\hat{z}_a - \hat{z}_b\|_2^2 = 2 - 2 \cdot \cos(\hat{z}_a, \hat{z}_b)$$
Fungsi kerugian dirumuskan sebagai:
$$\mathcal{L}_{\text{triplet}} = \max\left(0, \|\hat{z}_a - \hat{z}_p\|_2^2 - \|\hat{z}_a - \hat{z}_n\|_2^2 + m\right)$$
dengan batas margin hiperparameter $m = 0.3$.

### 3.3.3. Pelatihan Adversarial Dinamis (*Min-Max Optimization*)
Untuk mencegah *overfitting* pada derau statis, serangan diinjeksikan secara *on-the-fly* di dalam putaran pelatihan berdasarkan formulasi minimax (Madry et al., 2018):
$$\min_{\theta} \mathbb{E}_{(\mathbf{x}_a, \mathbf{x}_p, \mathbf{x}_n)} \left[ \max_{\|\boldsymbol{\delta}\|_\infty \le \epsilon} \mathcal{L}_{\text{triplet}}\left( f_\theta(\mathbf{x}_a), f_\theta(\mathbf{x}_p + \boldsymbol{\delta}), f_\theta(\mathbf{x}_n) \right) \right]$$

1. **Inner Maximization (PGD Step):** Menemukan perturbasi $\boldsymbol{\delta}$ yang memaksimumkan kerugian:
   $$\mathbf{x}_p^{(t+1)} = \Pi_{\mathbf{x}_p + \mathcal{S}} \left( \mathbf{x}_p^{(t)} + \alpha \cdot \text{sign}\left(\nabla_{\mathbf{x}_p^{(t)}} \mathcal{L}_{\text{triplet}}\right) \right)$$
   dengan anggaran $\epsilon = \frac{8}{255}$, ukuran langkah $\alpha = \frac{2}{255}$, dan iterasi $T = 3$.
2. **Outer Minimization (Model Weight Update):** Memperbarui bobot model $\theta$ menggunakan pengoptimal AdamW untuk meminimalkan kerugian pada citra positif terganggu $\mathbf{x}_p^{\text{adv}}$.

---

## 3.4. Desain Eksperimen dan Evaluasi Kinerja

### 3.4.1. Kalibrasi Ambang Batas (*Neyman-Pearson Thresholding*)
Ambang batas keputusan $\tau$ dikalibrasi secara eksklusif pada set Validasi ($\mathcal{B}_{\text{Val}}$) untuk mencegah bias pengujian:
$$\tau^* = \arg\max_\tau \text{Recall}(\tau) \quad \text{dengan kendala} \quad \text{FPR}(\tau) \le 0.01$$
Batasan operasional $\text{FPR} \le 1\%$ diadopsi untuk memitigasi kelelahan peringatan palsu (*alert fatigue*) pada analis SOC Komdigi. Nilai $\tau^*$ kemudian dikunci (*frozen*) sebelum diterapkan ke set Pengujian.

### 3.4.2. Metrik Evaluasi Kinerja
1. **Precision-Recall Area Under Curve (PR-AUC):** Metrik primer untuk mengevaluasi ketahanan diskriminasi pada distribusi kelas yang sangat tidak seimbang ($N_{\text{legal}} \gg N_{\text{phishing}}$):
   $$\text{PR-AUC} = \int_0^1 P(R) \, dR \approx \sum_{k=1}^K (R_k - R_{k-1}) P_k$$
2. **Recall @ Target FPR $\le$ 1%:** Sensitivitas deteksi aktual pada batas toleransi salah tangkap operasional.
3. **Robustness Gap ($\Delta_{\text{robust}}$):**
   $$\Delta_{\text{robust}} = \text{PR-AUC}_{\text{standard}} - \text{PR-AUC}_{\text{robust}}$$

### 3.4.3. Uji Signifikansi Statistik
* **Interval Kepercayaan Non-Parametrik Bootstrap:** Pengambilan sampel ulang dengan pengembalian (*resampling with replacement*) sebanyak $B = 1.000$ iterasi untuk menetapkan selang kepercayaan 95%:
  $$[\hat{\theta}^*_{2.5\%}, \hat{\theta}^*_{97.5\%}]$$
* **Uji Komparasi Model (DeLong / Paired Permutation Test):** Digunakan untuk menguji hipotesis nol ($H_0$) bahwa tidak terdapat perbedaan signifikan antara ketahanan model baseline standar dan model yang dilatih secara *adversarial*.

---

## 3.5. Arsitektur Implementasi Sistem (*Artifact Deployment*)

Luaran akhir dari penelitian ini diwujudkan dalam bentuk layanan mikro (*microservice*) inferensi berbasis **FastAPI**:

```
[ Input URL / Tangkapan Layar ]
              │
              ▼
    [ Playwright Sandbox ]
  (Isolasi Cookie, Alert Dismissal, Render Delay)
              │
              ▼
        [ YOLOv8 ]  ────────► (Lokalisasi & Pemotongan Bounding Box)
              │
              ▼
   [ Pre-computed Vector Index ] ◄── (Logo Kementerian Resmi L2-Normalized)
              │
              ▼
    [ Siamese ViT Engine ]
  (Ekstraksi Embedding 128-D & Cosine Distance)
              │
              ▼
   [ Decision Logic Engine ]
  (Periksa d_cos <= tau* AND Domain Unauthorized?)
              │
              ├─► "SUSPICIOUS_PHISHING" (Pencatutan Merek Ilegal)
              └─► "LEGITIMATE"          (Domain Resmi Terverifikasi)
```

1. **Pre-computed Embeddings:** Saat startup, seluruh logo referensi diproyeksikan sekali ke memori RAM, mereduksi waktu inferensi per request menjadi $< 100$ ms.
2. **Kontainerisasi (Docker):** Seluruh *dependency* dibungkus dalam kontainer Docker untuk simulasi integrasi dengan sistem AduanKonten.id Komdigi.
