# 进阶挑战 ③ —— NMOS 共源级放大电路

## 一、参数

$$V_{DD}=5\ \text{V},\quad R_{g1}=60\ \text{k}\Omega,\quad R_{g2}=40\ \text{k}\Omega,\quad R_d=2\ \text{k}\Omega$$

$$K=0.8\ \text{mA/V}^2,\quad V_{th}=1\ \text{V},\quad \lambda=0.02\ /\text{V}$$

$$V_i = 10\ \text{mV 峰值},\quad f = 1\ \text{kHz},\quad C_b\ \text{足够大（取}\ 1\ \mu\text{F）}$$

![共源放大电路](nmos_circuit.png)

![小信号等效模型](nmos_small_signal.png)

---

## 二、公式与计算

### 1. 栅极偏置

$$V_{GS} = V_{DD}\cdot\frac{R_{g2}}{R_{g1}+R_{g2}}$$

$$V_{GS} = 5\times\frac{40}{60+40} = 2.0\ \text{V}$$

$$V_{ov} = V_{GS} - V_{th} = 2.0 - 1.0 = 1.0\ \text{V}$$

### 2. 漏极电流（先忽略 λ）

$$I_D = K\cdot V_{ov}^2$$

$$I_D = 0.8\times10^{-3}\times(1.0)^2 = 0.8\ \text{mA}$$

### 3. 漏源电压

$$V_{DS} = V_{DD} - I_D R_d$$

$$V_{DS} = 5 - 0.8\times10^{-3}\times2000 = 3.4\ \text{V}$$

### 4. 饱和区判断

$$V_{DS} > V_{ov}\ ?$$

$$3.4\ \text{V} > 1.0\ \text{V}\ \Rightarrow\ \text{工作在饱和区}\ \checkmark$$

### 5. 含 λ 的精确解

$$I_D = KV_{ov}^2(1+\lambda V_{DS}),\qquad V_{DS} = V_{DD} - I_D R_d$$

$$I_D = \frac{KV_{ov}^2(1+\lambda V_{DD})}{1 + KV_{ov}^2\lambda R_d}$$

$$I_D = \frac{0.8\times10^{-3}\times1.02}{1 + 0.8\times10^{-3}\times0.02\times2000} = 0.8527\ \text{mA}$$

$$V_{DS} = 5 - 0.8527\times10^{-3}\times2000 = 3.2946\ \text{V}$$

### 6. 跨导 g_m

$$\text{① 忽略 } \lambda:\quad g_m = \frac{\partial I_D}{\partial V_{GS}} = 2KV_{ov}$$

$$g_m = 2\times0.8\times10^{-3}\times1.0 = 1.6\ \text{mA/V}$$

$$\text{② 含 } \lambda:\quad g_m = 2KV_{ov}(1+\lambda V_{DS})$$

$$g_m = 1.6\times10^{-3}\times(1+0.02\times3.2946) = 1.7054\ \text{mA/V}$$

### 7. 输出电阻 r_o

$$r_o = \frac{1}{\lambda I_D}$$

$$r_o = \frac{1}{0.02\times0.8\times10^{-3}} = 62.5\ \text{k}\Omega$$

### 8. 电压增益 A_v

$$R_d \parallel r_o = \frac{R_d\, r_o}{R_d + r_o} = \frac{2\times62.5}{2+62.5} = 1.938\ \text{k}\Omega$$

$$A_v = -g_m(R_d \parallel r_o)$$

$$A_v = -1.7054\times10^{-3}\times1.938\times10^{3} = -3.3051\ \text{V/V}$$

$$|A_v| = 3.3051 = 10.38\ \text{dB},\qquad \varphi = 180°$$

### 9. 输出幅度

$$V_{out} = |A_v|\cdot V_{in} = 3.3051\times20\ \text{mVpp} = 66.1\ \text{mVpp}$$

### 10. 线性度检查

$$V_{DS} - V_{ov} = 3.2946 - 1.0 = 2.29\ \text{V}\ \gg\ 33\ \text{mV}\ \Rightarrow\ \text{不削顶}$$

---

## 三、仿真结果

![瞬态波形](nmos_transient.png)

![交流扫描](nmos_ac.png)

### 交流扫描各频点

$$|A_v(f)| = \left| -g_m(R_d \parallel r_o)\cdot\frac{j\omega R_{in}C_b}{1+j\omega R_{in}C_b}\right|$$

| f | \|A_v\| | dB | 相位 |
|---:|---:|---:|---:|
| 1 Hz | 0.4858 | −6.27 | −89.55° |
| 10 Hz | 2.7488 | 8.78 | −145.54° |
| 100 Hz | 3.2915 | 10.35 | −176.12° |
| 1 kHz | 3.2986 | 10.37 | −179.61° |
| 10 kHz | 3.2987 | 10.37 | −179.96° |
| 100 kHz | 3.2987 | 10.37 | −180.00° |

$$C_b\ \text{容抗（1 kHz）} = \frac{1}{2\pi f C_b} = 159.2\ \Omega\ \ll\ R_{g1}\parallel R_{g2} = 24\ \text{k}\Omega$$

---

## 四、对比表 1：静态工作点与饱和区判断

| 指标 | 手算值 | 仿真值 | 相对误差 |
|---|---:|---:|---:|
| V_GS (=V_G) (V) | 2.00000 | 2.00000 | 0.0000% |
| I_D (mA) | 0.85271 | 0.85271 | 0.0000% |
| V_DS (=V_d) (V) | 3.29457 | 3.29457 | 0.0000% |
| V_ov (V) | 1.0000 | 1.0000 | 0.0000% |
| 饱和区判断 | V_DS > V_ov 成立 | V_DS > V_ov 成立 | 一致 |

$$I_D = \frac{V_{DD} - V_{DS}}{R_d} = \frac{5-3.29457}{2000} = 0.85271\ \text{mA}$$

---

## 五、对比表 2：小信号 gm、r_o 与增益

| 指标 | 手算值 | 仿真值 | 相对误差 |
|---|---:|---:|---:|
| g_m ① 2K·V_ov (mA/V) | 1.60000 | 1.70543 | **6.5892%** |
| g_m ② 含 λ (mA/V) | 1.70543 | 1.70543 | **0.0000%** |
| r_o = 1/(λ·I_D) (kΩ) | 62.50000 | 62.50000 | 0.0000% |
| R_d‖r_o (kΩ) | 1.93798 | 1.93798 | 0.0000% |
| \|A_v\| 用①的手算 | 3.10078 | 3.29827 | 6.3691% |
| \|A_v\| 用②的手算 | 3.30509 | 3.29827 | **0.2064%** |
| \|A_v\| 由仿真的 gm、r_o | 3.30509 | 3.29827 | 0.2065% |
| \|A_v\| 交流扫描（对照） | 3.30509 | 3.29862 | 0.1956% |

$$\text{瞬态实测：}\ |A_v| = \frac{V_{out,pp}}{V_{in,pp}} = \frac{65.9649}{19.9999} = 3.2983$$

$$\text{相关系数}\ \rho(v_{in}, v_{out}) = -1.0000\ \Rightarrow\ \text{反相}\ 180°$$

---

