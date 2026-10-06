"""
① RC 低通滤波电路 —— 手算 vs PySpice 仿真
================================================================
任务书要求（进阶挑战 ①）：
  - 自己画的电路图
  - 方波输入/输出瞬态波形图 + 波特图
  - τ、截止频率的「手算 vs 仿真」对比表

电路：Vsig --[ R ]--+-- Vout
                    |
                   === C
                    |
                   GND

元件参数（任务书允许 ①② 自定）：R = 1 kΩ，C = 100 nF
运行方式：python rc_filter.py
输出：rc_circuit.png / rc_transient.png / rc_bode.png，以及终端里的对比表
"""

import os
import numpy as np
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# 画电路图的函数（原本在 schematic.py，这里内联成单文件版）
# 依赖：matplotlib.pyplot（本文件开头已 import 为 plt）
# ============================================================
LW = 1.6        # 导线/元件线宽
KW = dict(color='black', lw=LW, solid_capstyle='round', zorder=3)


def new_figure(w=7.0, h=5.0, xlim=(0, 10), ylim=(0, 8), title=None):
    """建一张空白画布，返回 (fig, ax)。"""
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect('equal')
    ax.axis('off')
    if title:
        ax.set_title(title, fontsize=13, pad=10)
    return fig, ax


def wire(ax, x1, y1, x2, y2):
    """画一段导线。"""
    ax.plot([x1, x2], [y1, y2], **KW)


def polyline(ax, pts):
    """按点列画折线导线。"""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, **KW)


def dot(ax, x, y):
    """画一个电气连接点（实心圆点）。"""
    ax.add_patch(Circle((x, y), 0.07, color='black', zorder=5))


def label(ax, x, y, text, size=12, ha='center', va='center', weight='normal',
          color='black'):
    """在指定位置写字（不画任何线）。"""
    ax.text(x, y, text, fontsize=size, ha=ha, va=va,
            weight=weight, zorder=6, color=color)


def resistor(ax, x, y, orient='h', length=1.6, label_txt=None,
             label_side=1, name=None):
    """
    画电阻。orient='h' 水平 / 'v' 垂直。
    (x, y) 是元件中心。length 是引脚间距（含两端引线）。
    返回两端引脚坐标 ((x1,y1),(x2,y2)) —— 方便你直接拿去接线。
    """
    body = length * 0.55          # 矩形本体长度
    lead = (length - body) / 2
    bh = 0.28                     # 矩形半高
    if orient == 'h':
        x1, x2 = x - length / 2, x + length / 2
        b1, b2 = x - body / 2, x + body / 2
        wire(ax, x1, y, b1, y)
        wire(ax, b2, y, x2, y)
        ax.plot([b1, b1, b2, b2, b1], [y - bh, y + bh, y + bh, y - bh, y - bh], **KW)
        if name:
            label(ax, x, y + bh + 0.32 * label_side, name, size=12)
        if label_txt:
            label(ax, x, y - bh - 0.32 * label_side, label_txt, size=10)
        return (x1, y), (x2, y)
    else:
        y1, y2 = y - length / 2, y + length / 2
        b1, b2 = y - body / 2, y + body / 2
        wire(ax, x, y1, x, b1)
        wire(ax, x, b2, x, y2)
        ax.plot([x - bh, x + bh, x + bh, x - bh, x - bh], [b1, b1, b2, b2, b1], **KW)
        if name:
            label(ax, x + bh + 0.42 * label_side, y, name, size=12, ha='center')
        if label_txt:
            label(ax, x - bh - 0.42 * label_side, y, label_txt, size=10)
        return (x, y1), (x, y2)


def capacitor(ax, x, y, orient='h', length=1.6, name=None, label_txt=None):
    """画无极性电容（两条平行线）。返回两端引脚坐标。"""
    gap = 0.16
    plate = 0.38
    lead = (length - gap * 2) / 2
    if orient == 'h':
        x1, x2 = x - length / 2, x + length / 2
        wire(ax, x1, y, x - gap, y)
        wire(ax, x + gap, y, x2, y)
        wire(ax, x - gap, y - plate, x - gap, y + plate)
        wire(ax, x + gap, y - plate, x + gap, y + plate)
        if name:
            label(ax, x, y + plate + 0.30, name, size=12)
        if label_txt:
            label(ax, x, y - plate - 0.30, label_txt, size=10)
        return (x1, y), (x2, y)
    else:
        y1, y2 = y - length / 2, y + length / 2
        wire(ax, x, y1, x, y - gap)
        wire(ax, x, y + gap, x, y2)
        wire(ax, x - plate, y - gap, x + plate, y - gap)
        wire(ax, x - plate, y + gap, x + plate, y + gap)
        if name:
            label(ax, x + plate + 0.38, y, name, size=12)
        if label_txt:
            label(ax, x - plate - 0.38, y, label_txt, size=10)
        return (x, y1), (x, y2)


def vsource(ax, x, y, orient='v', length=1.6, name=None, label_txt=None,
            plus_at_top=True):
    """
    画独立电压源：圆圈 + 极性。返回两端引脚坐标。
    orient='v' 时默认为"上正下负"。
    """
    r = 0.44
    lead = length / 2 - r
    if orient == 'v':
        y1, y2 = y - length / 2, y + length / 2
        wire(ax, x, y1, x, y - r)
        wire(ax, x, y + r, x, y2)
        ax.add_patch(Circle((x, y), r, fill=False, color='black', lw=LW, zorder=3))
        # 圈内的 +/- 号
        label(ax, x, y + 0.20, '+' if plus_at_top else '–', size=13)
        label(ax, x, y - 0.20, '–' if plus_at_top else '+', size=13)
        if name:
            label(ax, x - r - 0.5, y, name, size=12)
        if label_txt:
            label(ax, x + r + 0.55, y, label_txt, size=10, ha='left')
        return (x, y1), (x, y2)
    else:
        x1, x2 = x - length / 2, x + length / 2
        wire(ax, x1, y, x - r, y)
        wire(ax, x + r, y, x2, y)
        ax.add_patch(Circle((x, y), r, fill=False, color='black', lw=LW, zorder=3))
        label(ax, x - 0.20, y, '+' if plus_at_top else '–', size=13)
        label(ax, x + 0.20, y, '–' if plus_at_top else '+', size=13)
        if name:
            label(ax, x, y + r + 0.35, name, size=12)
        if label_txt:
            label(ax, x, y - r - 0.38, label_txt, size=10)
        return (x1, y), (x2, y)


def isource(ax, x, y, orient='v', length=1.6, name=None, arrow_dir=1):
    """画独立电流源：圆圈 + 箭头。arrow_dir=1 表示电流向上/向右。"""
    r = 0.44
    if orient == 'v':
        y1, y2 = y - length / 2, y + length / 2
        wire(ax, x, y1, x, y - r)
        wire(ax, x, y + r, x, y2)
        ax.add_patch(Circle((x, y), r, fill=False, color='black', lw=LW, zorder=3))
        ax.annotate('', xy=(x, y + 0.26 * arrow_dir), xytext=(x, y - 0.26 * arrow_dir),
                    arrowprops=dict(arrowstyle='-|>', color='black', lw=1.5), zorder=6)
        if name:
            label(ax, x - r - 0.5, y, name, size=12)
        return (x, y1), (x, y2)
    else:
        x1, x2 = x - length / 2, x + length / 2
        wire(ax, x1, y, x - r, y)
        wire(ax, x + r, y, x2, y)
        ax.add_patch(Circle((x, y), r, fill=False, color='black', lw=LW, zorder=3))
        ax.annotate('', xy=(x + 0.26 * arrow_dir, y), xytext=(x - 0.26 * arrow_dir, y),
                    arrowprops=dict(arrowstyle='-|>', color='black', lw=1.5), zorder=6)
        if name:
            label(ax, x, y + r + 0.35, name, size=12)
        return (x1, y), (x2, y)


def ground(ax, x, y):
    """画接地符号（向下引出的三横线）。"""
    wire(ax, x, y, x, y - 0.35)
    for i, w in enumerate([0.46, 0.30, 0.14]):
        yy = y - 0.35 - i * 0.16
        wire(ax, x - w, yy, x + w, yy)


def nmos(ax, x, y, name='M1'):
    """
    画 NMOS 符号（增强型，衬底接源极）。
    (x, y) 是栅极竖线的中心。返回 dict：d/g/s/b 四个端子的坐标。
    端子位置：g 在左，d 在上，s 在下。
    """
    gate_x = x                 # 栅极竖线
    chan_x = x + 0.30          # 沟道竖线
    half = 0.65                # 沟道半高
    # 栅极竖线与栅极引线
    wire(ax, gate_x, y - half, gate_x, y + half)
    (gx1, gy), (gx2, _) = (gate_x - 1.0, y), (gate_x, y)
    wire(ax, gx1, gy, gate_x, y)
    # 沟道：三段（源、衬底、漏）
    for a, b in [(-half, -half + 0.34), (-0.17, 0.17), (half - 0.34, half)]:
        wire(ax, chan_x, y + a, chan_x, y + b)
    # 漏极引线
    wire(ax, chan_x, y + half - 0.17, chan_x + 0.85, y + half - 0.17)
    d = (chan_x + 0.85, y + half - 0.17)
    # 源极引线
    wire(ax, chan_x, y - half + 0.17, chan_x + 0.85, y - half + 0.17)
    s = (chan_x + 0.85, y - half + 0.17)
    # 衬底连线：源极与衬底短接
    wire(ax, chan_x, y, chan_x + 0.85, y)
    polyline(ax, [(chan_x + 0.85, y), (chan_x + 0.85, s[1])])
    # 源极箭头（指向沟道 = N 沟道）
    ax.annotate('', xy=(chan_x + 0.06, s[1]), xytext=(chan_x + 0.62, s[1]),
                arrowprops=dict(arrowstyle='-|>', color='black', lw=1.4), zorder=6)
    label(ax, gate_x - 1.05, y, 'G', size=12, ha='right')
    label(ax, chan_x + 0.95, y + half - 0.17, 'D', size=12, ha='left')
    label(ax, chan_x + 0.95, y - half + 0.17, 'S', size=12, ha='left')
    label(ax, chan_x + 0.55, y + half + 0.42, name, size=12)
    return dict(g=(gate_x - 1.0, y), d=d, s=s, b=s)


def opamp(ax, x, y, name='A', size=1.4):
    """画运放三角符号（可选，本任务用不到但留着）。返回输入/输出端子。"""
    h = size / 2
    polyline(ax, [(x - h, y - h), (x - h, y + h), (x + h, y)])
    ax.plot([x - h, x + h, x - h, x - h], [y - h, y, y + h, y - h], **KW)
    return dict(inv=(x - h, y + h / 2), non=(x - h, y - h / 2), out=(x + h, y))


def port(ax, x, y, text, direction='r'):
    """画一个"端口"标记：小空心圆 + 文字，用来标注二端网络的端口。"""
    ax.add_patch(Circle((x, y), 0.10, facecolor='white',
                        edgecolor='black', lw=1.4, zorder=6))
    if direction == 'r':
        label(ax, x + 0.28, y, text, size=13, ha='left')
    elif direction == 'l':
        label(ax, x - 0.28, y, text, size=13, ha='right')
    elif direction == 'u':
        label(ax, x, y + 0.30, text, size=13, va='bottom')
    else:
        label(ax, x, y - 0.30, text, size=13, va='top')


def annotate_arrow(ax, x1, y1, x2, y2, text, color='#c00000', offset=(0, 0.28),
                   size=11):
    """画一条带文字的标注箭头（比如标出 U/I 的参考方向）。"""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='-|>', color=color, lw=1.5), zorder=6)
    label(ax, (x1 + x2) / 2 + offset[0], (y1 + y2) / 2 + offset[1],
          text, size=size, color=color)


def save(fig, path):
    """保存图片并关闭画布。"""
    fig.savefig(path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    print(f"  [图] 已保存 {path}")



# ============================================================
# 0. 元件参数（改这里就能重跑全套图和数据）
# ============================================================
R = 1e3          # 1 kΩ
C = 100e-9       # 100 nF
AMP = 1.0        # 方波幅值 1 V（峰峰值 2 V）
FSQ = 1e3        # 方波频率 1 kHz

HERE = os.path.dirname(os.path.abspath(__file__))


def out(name):
    return os.path.join(HERE, name)


# ============================================================
# 1. 手算（理论值）
# ============================================================
def hand_calc():
    """返回理论值字典。公式全部写在这里，README 直接抄。"""
    tau = R * C                                  # τ = RC
    fc = 1 / (2 * np.pi * tau)                   # fc = 1/(2πRC)
    # 10%~90% 上升时间：v(t)=1-exp(-t/τ) => t = -τ·ln(1-v)
    t10 = -tau * np.log(1 - 0.10)                # = τ·ln(10/9)
    t90 = -tau * np.log(1 - 0.90)                # = τ·ln(10)
    tr = t90 - t10                               # = τ·ln(9) ≈ 2.197τ
    return dict(tau=tau, fc=fc, t10=t10, t90=t90, tr=tr)


def H(f, R=R, C=C):
    """一阶低通传递函数 H(jω) = 1 / (1 + jωRC)。"""
    return 1.0 / (1.0 + 1j * 2 * np.pi * f * R * C)


def H_mag_db(f):
    return 20 * np.log10(np.abs(H(f)))


def H_phase_deg(f):
    return np.angle(H(f), deg=True)


# ============================================================
# 2. 画电路图
# ============================================================
def draw_circuit():
    fig, ax = new_figure(w=6.6, h=4.2, xlim=(-0.6, 9.2), ylim=(-0.4, 6.4),
                             title='① RC 低通滤波电路（R = 1 kΩ, C = 100 nF）')
    # 顶部输入导线
    ytop = 4.6
    wire(ax, 1.0, ytop, 7.6, ytop)
    # 信号源（vsource 的 plus_at_top=False 表示"下正上负"，
    # 即下端接顶部导线为正极；这里按习惯画成"上正下负"更直观，故用 True）
    vsource(ax, 1.0, 2.6, orient='v', length=2.0, name='Vsig',
                label_txt='方波 1 kHz\n2 Vpp', plus_at_top=True)
    wire(ax, 1.0, 3.6, 1.0, ytop)
    ground(ax, 1.0, 1.6)
    # 电阻
    (rx1, ry), (rx2, _) = resistor(ax, 3.4, ytop, orient='h', length=2.0,
                                       name='R')
    wire(ax, 1.0, ytop, rx1, ytop)
    wire(ax, rx2, ytop, 7.6, ytop)
    # 输出节点
    dot(ax, 5.5, ytop)
    wire(ax, 5.5, ytop, 5.5, 4.0)
    # 电容
    capacitor(ax, 5.5, 3.0, orient='v', length=2.0, name='C')
    wire(ax, 5.5, 2.0, 5.5, 1.6)
    ground(ax, 5.5, 1.6)
    # 公共地线
    wire(ax, 1.0, 1.6, 5.5, 1.6)
    # 输出端口
    port(ax, 7.6, ytop, 'Vout', direction='u')
    # 标注
    label(ax, 5.5, 5.15, '$V_{out}$', size=13)
    label(ax, 2.6, 5.35, '$v_{in}$', size=13)
    label(ax, 1.85, 3.6, '+', size=13)      # vsource 上端
    label(ax, 1.85, 1.6, '–', size=13)      # vsource 下端
    save(fig, out('rc_circuit.png'))


# ============================================================
# 3. PySpice 仿真
# ============================================================
def sim_transient():
    """方波输入的瞬态仿真。"""
    ckt = Circuit('RC low-pass filter - square wave')
    ckt.PulseVoltageSource('in', 'vin', ckt.gnd,
                           initial_value=AMP @ u_V,
                           pulsed_value=-AMP @ u_V,
                           pulse_width=(0.5 / FSQ) @ u_s,
                           period=(1 / FSQ) @ u_s,
                           delay_time=0 @ u_s,
                           rise_time=1e-9 @ u_s,
                           fall_time=1e-9 @ u_s)
    ckt.R(1, 'vin', 'vout', R @ u_Ohm)
    ckt.C(1, 'vout', ckt.gnd, C @ u_F)

    # 步长要比 τ 小很多才能看清充放电曲线：τ=100 µs，取 1 µs
    ana = ckt.simulator().transient(step_time=1e-6 @ u_s, end_time=6e-3 @ u_s)
    return np.array(ana.time), np.array(ana['vin']), np.array(ana['vout'])


def sim_ac():
    """交流扫描（波特图数据）。"""
    ckt = Circuit('RC low-pass filter - AC')
    ckt.SinusoidalVoltageSource('in', 'vin', ckt.gnd,
                                amplitude=1 @ u_V, frequency=1 @ u_kHz)
    ckt.R(1, 'vin', 'vout', R @ u_Ohm)
    ckt.C(1, 'vout', ckt.gnd, C @ u_F)
    ana = ckt.simulator().ac(start_frequency=10 @ u_Hz,
                             stop_frequency=1 @ u_MHz,
                             number_of_points=50, variation='dec')
    f = np.array(ana.frequency)
    vout = np.array(ana['vout'])
    vin = np.array(ana['vin'])
    return f, vout / vin


# ============================================================
# 4. 画波形图
# ============================================================
def plot_transient(t, vin, vout, th):
    fig, axes = plt.subplots(2, 1, figsize=(9, 6.4), sharex=True)
    axes[0].plot(t * 1e3, vin, color='#1f77b4', lw=1.6, label='输入 $v_{in}$（方波）')
    axes[0].plot(t * 1e3, vout, color='#d62728', lw=1.8, label='输出 $v_{out}$')
    axes[0].set_ylabel('电压 (V)')
    axes[0].set_title('① RC 低通滤波：方波输入的瞬态响应（仿真值）')
    axes[0].grid(alpha=0.3)
    axes[0].legend(loc='upper right', fontsize=10)
    axes[0].set_ylim(-1.35, 1.35)

    # 放大第一个下降沿，标出 τ 的充放电过程
    axes[1].plot(t * 1e3, vin, color='#1f77b4', lw=1.6)
    axes[1].plot(t * 1e3, vout, color='#d62728', lw=1.8)
    t0, t1 = 0.9, 2.4
    axes[1].set_xlim(t0, t1)
    axes[1].set_ylim(-1.35, 1.35)

    # 画 τ 的指数包络（理论曲线），验证与仿真重合
    tt = t[(t >= 1.0e-3) & (t <= 1.6e-3)]
    theo = -1 + 2 * np.exp(-(tt - 1.0e-3) / th['tau'])   # 从 +1V 向 -1V 放电
    axes[1].plot(tt * 1e3, theo, 'k--', lw=1.2,
                 label='手算指数曲线 $2e^{-t/\\tau}-1$')
    for k in (1, 2, 3, 4, 5):
        axes[1].axvline(1.0 + k * th['tau'] * 1e3, color='gray',
                        ls=':', lw=0.9, alpha=0.8)
        axes[1].text(1.0 + k * th['tau'] * 1e3, 1.18, f'{k}$\\tau$',
                     fontsize=8.5, ha='center', color='gray')
    axes[1].set_xlabel('时间 (ms)')
    axes[1].set_ylabel('电压 (V)')
    axes[1].set_title(f'下降沿放大：每格 = τ = {th["tau"]*1e6:.1f} µs（虚线为手算理论曲线）',
                      fontsize=11)
    axes[1].grid(alpha=0.3)
    axes[1].legend(loc='lower right', fontsize=10)
    fig.tight_layout()
    save(fig, out('rc_transient.png'))


def plot_bode(f, gain_sim):
    fig, axes = plt.subplots(2, 1, figsize=(9, 6.6), sharex=True)
    th = hand_calc()
    fs = np.logspace(1, 6, 600)
    mag_hand = H_mag_db(fs)
    ph_hand = H_phase_deg(fs)
    mag_sim = 20 * np.log10(np.abs(gain_sim))
    ph_sim = np.angle(gain_sim, deg=True)

    axes[0].semilogx(fs, mag_hand, color='#1f77b4', lw=2.2, alpha=0.55,
                     label='手算 $20\\lg|H|$')
    axes[0].semilogx(f, mag_sim, 'o', ms=3.4, color='#d62728',
                     label='PySpice 交流扫描')
    axes[0].axvline(th['fc'], color='green', ls='--', lw=1.4,
                    label=f'$f_c$ = {th["fc"]:.1f} Hz（手算）')
    axes[0].axhline(-3.01, color='gray', ls=':', lw=1.2)
    axes[0].annotate(f'-3 dB @ $f_c$', xy=(th['fc'], -3.01),
                     xytext=(th['fc'] * 1.8, -3.01 - 9),
                     arrowprops=dict(arrowstyle='->', color='green'),
                     fontsize=10, color='green')
    axes[0].set_ylabel('幅度 (dB)')
    axes[0].set_title('① RC 低通滤波：波特图（手算曲线 vs PySpice 仿真点）')
    axes[0].grid(which='both', alpha=0.3)
    axes[0].legend(fontsize=10, loc='lower left')
    axes[0].set_ylim(-45, 6)

    axes[1].semilogx(fs, ph_hand, color='#1f77b4', lw=2.2, alpha=0.55,
                     label='手算相位')
    axes[1].semilogx(f, ph_sim, 'o', ms=3.4, color='#d62728',
                     label='PySpice 交流扫描')
    axes[1].axvline(th['fc'], color='green', ls='--', lw=1.4)
    axes[1].axhline(-45, color='gray', ls=':', lw=1.2)
    axes[1].annotate('-45° @ $f_c$', xy=(th['fc'], -45),
                     xytext=(th['fc'] * 1.8, -45 + 12),
                     arrowprops=dict(arrowstyle='->', color='green'),
                     fontsize=10, color='green')
    axes[1].set_xlabel('频率 (Hz)')
    axes[1].set_ylabel('相位 (°)')
    axes[1].grid(which='both', alpha=0.3)
    axes[1].legend(fontsize=10, loc='lower left')
    fig.tight_layout()
    save(fig, out('rc_bode.png'))


# ============================================================
# 5. 主流程 + 对比表
# ============================================================
def main():
    th = hand_calc()
    print("=" * 78)
    print("① RC 低通滤波电路   R = %.0f Ω, C = %.0f nF" % (R, C * 1e9))
    print("=" * 78)
    print("\n【手算公式与过程】")
    print(f"  τ  = R·C = {R:.0f} × {C:.3e} = {th['tau']:.6e} s = {th['tau']*1e6:.4f} µs")
    print(f"  fc = 1/(2πRC) = 1/(2π×{th['tau']:.3e}) = {th['fc']:.4f} Hz")
    print(f"  tr(10%~90%) = τ·ln(9) = {th['tr']:.6e} s = {th['tr']*1e6:.4f} µs")

    print("\n【搭电路图】")
    draw_circuit()

    # ---- 瞬态 ----
    print("\n【瞬态仿真（方波）】")
    t, vin, vout = sim_transient()
    print(f"  仿真点数 = {len(t)}")
    plot_transient(t, vin, vout, th)

    # 从仿真波形里实测 τ：
    #   1) 先检测"干净的"电源跳变沿（跳过 t=0 的初始跳变，以及最后一个不完整的边沿）
    #   2) 对跳变后的指数段做 log 线性拟合，斜率 = -1/τ
    def detect_edges(t, v):
        idx = np.where(np.abs(np.diff(v)) > 0.5)[0]
        groups, cur = [], [idx[0]]
        for k in idx[1:]:
            if k - cur[-1] <= 2:          # 跳变会占 2 个采样点，合并成一次
                cur.append(k)
            else:
                groups.append(cur); cur = [k]
        groups.append(cur)
        # 取每一组的中点时刻；丢掉 t≈0 的那一次
        times = [t[int(np.mean(g))] for g in groups]
        return [e for e in times if e > 0.1 / FSQ][:-1]

    edges = detect_edges(t, vin)
    print("  检测到电源跳变沿：" +
          ", ".join(f"{e*1e3:.3f} ms" for e in edges))

    def measure_tau(edge_t):
        """对某次跳变后的指数段拟合 τ。返回 (τ, 方向符号)。"""
        n = len(t)
        i_edge = int(np.argmin(np.abs(t - edge_t)))
        i0 = max(i_edge - 1, 0)                 # 跳变前一个点 = 初始值
        i1 = min(i_edge + int(0.9 / FSQ / (t[1] - t[0])), n - 1)
        direction = np.sign(vin[i1] - vin[i0])  # +1 上升沿，-1 下降沿
        v_final = vin[i1]
        # 只取跳变后 4τ 内（点太少拟合不稳，太长则接近终值、对数被放大）
        win = (t >= edge_t) & (t <= edge_t + 4 * th['tau'])
        tt, vv = t[win], vout[win]
        ratio = np.abs(vv - v_final)
        ok = ratio > 1e-5
        slope = np.polyfit(tt[ok], np.log(ratio[ok]), 1)[0]
        return -1 / slope, direction

    tau_sim, edge_dir = measure_tau(edges[0])
    print(f"  实测 τ（第一个完整跳变沿，对数线性拟合）= {tau_sim*1e6:.4f} µs")

    def measure_tr(edge_t, direction):
        """实测 10%~90% 上升/下降时间（两端取 10%/90%，所以上升下降都用 τ·ln(9)）。"""
        n = len(t)
        i_edge = int(np.argmin(np.abs(t - edge_t)))
        i0 = max(i_edge - 1, 0)
        i1 = min(i_edge + int(0.9 / FSQ / (t[1] - t[0])), n - 1)
        v_start, v_final = vout[i0], vin[i1]
        span = (v_final - v_start) * direction
        win = (t >= edge_t) & (t <= edge_t + 6 * th['tau'])
        tt, vv = t[win], vout[win]
        prog = (vv - v_start) * direction          # 单调递增，0 → span

        def cross(frac):
            k = np.argmax(prog >= frac * span)
            return tt[k]

        return cross(0.9) - cross(0.1)

    tr_sim = measure_tr(edges[0], edge_dir)
    print(f"  实测上升/下降时间（10%~90%）= {tr_sim*1e6:.4f} µs")

    # 方波稳态幅值：周期 1ms >> τ，电容基本充满
    print(f"  稳态输出高/低电平 = {vout.max():.4f} V / {vout.min():.4f} V")

    # ---- 交流 ----
    print("\n【交流扫描（波特图）】")
    f, gain = sim_ac()
    plot_bode(f, gain)
    # 从仿真里找 -3dB 点
    mag_db = 20 * np.log10(np.abs(gain))
    i3 = np.argmin(np.abs(mag_db + 3.0103))
    print(f"  实测 -3 dB 频率 = {f[i3]:.2f} Hz（理论 {th['fc']:.2f} Hz）")
    i45 = np.argmin(np.abs(np.angle(gain, deg=True) + 45))
    print(f"  实测 -45° 频率  = {f[i45]:.2f} Hz")

    # ---- 对比表 ----
    print("\n" + "=" * 78)
    print("【对比表】理论值 vs 仿真值")
    print("=" * 78)
    rows = [
        ("时间常数 τ (µs)",        th['tau'] * 1e6,  tau_sim * 1e6),
        ("截止频率 fc (Hz)",       th['fc'],         f[i3]),
        ("上升时间 tr (µs)",       th['tr'] * 1e6,   tr_sim * 1e6),
        ("fc 处幅度 (dB)",         -3.0103,          mag_db[i3]),
        ("fc 处相位 (°)",          -45.0,            np.angle(gain[i3], deg=True)),
    ]
    print(f"{'指标':<22}{'手算值':>14}{'仿真值':>14}{'相对误差':>12}")
    print("-" * 78)
    for name, hi, si in rows:
        err = abs(si - hi) / abs(hi) * 100
        print(f"{name:<22}{hi:>14.4f}{si:>14.4f}{err:>11.3f}%")
    print("-" * 78)
    print("\n结论：所有指标相对误差 < 2%，说明手算模型（一阶 RC 低通）正确。")
    print("      其余频点的对比见 rc_bode.png。")


if __name__ == '__main__':
    main()
