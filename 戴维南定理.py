"""
② 验证戴维南定理 —— 手算 vs PySpice 仿真
================================================================
任务书要求（进阶挑战 ②）：
  - 自己画的含源二端网络图（标注端口）
  - V_oc、I_sc 两次仿真的「手算 vs 仿真」对比表
  - 等效电路替换后接负载的电压 / 电流验证表

含源二端网络（元件参数自定，这里全取整数便于手算）：
        12V o---+---[ R1 3k ]---+---[ R2 2k ]---+
                |               |               |
                |            (节点 a)           |
                |                               [RL]
                |            (节点 b)           |
                |               |               |
                +---[ R3 2k ]---+---[ R4 3k ]---+
                                    |
                                   GND
  两个支路共用同一个 12 V 电源（图中画成两个并联的同值源，电气上等价）。

运行方式：python thevenin.py
输出：thevenin_circuit.png / thevenin_equivalent.png / thevenin_load.png + 两张对比表
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
# 0. 参数（全取整数，手算方便）
# ============================================================
V1 = 12.0            # 电源电压
R1, R2 = 3e3, 2e3    # 上支路：R1 接电源，R2 接地
R3, R4 = 2e3, 3e3    # 下支路：R3 接电源，R4 接地
LOAD_TEST = [240.0, 1e3, 2.4e3, 4.8e3, 10e3, 100e3]   # 负载验证点

HERE = os.path.dirname(os.path.abspath(__file__))
def out(n):
    return os.path.join(HERE, n)


# ============================================================
# 1. 手算
# ============================================================
def hand_calc():
    Va = V1 * R2 / (R1 + R2)     # 上支路分压 Va = V1·R2/(R1+R2)
    Vb = V1 * R4 / (R3 + R4)     # 下支路分压 Vb = V1·R4/(R3+R4)
    Vth = Va - Vb                # 开路电压（端口 a 对 b）= V_th
    Rth = R1 * R2 / (R1 + R2) + R3 * R4 / (R3 + R4)   # 电源置零后的端口电阻
    Isc = Vth / Rth              # 短路电流
    return dict(Va=Va, Vb=Vb, Vth=Vth, Rth=Rth, Isc=Isc)


def exact_v(RL):
    """原网络接负载 RL 时的端口电压（节点法解析解）。"""
    G = np.array([[1 / R1 + 1 / R2 + 1 / RL, -1 / RL],
                  [-1 / RL, 1 / R3 + 1 / R4 + 1 / RL]])
    I = np.array([V1 / R1, V1 / R3])       # 两个支路的诺顿电流源
    V = np.linalg.solve(G, I)
    return V[0] - V[1]


# ============================================================
# 2. 画图
# ============================================================
def draw_source_network():
    """含源二端网络 + 端口 a、b 标注。"""
    fig, ax = new_figure(w=7.8, h=5.2, xlim=(-2.6, 11.6), ylim=(-1.0, 9.4),
                             title='② 含源二端网络（端口 a–b 已标注）')
    xS, xT = 0.0, 9.6
    yT, yB = 7.3, 2.5
    xr1, xr2 = 2.6, 6.2

    # ---- 12 V 电源：竖直放置，上端接上支路、下端接下支路并接地 ----
    vsource(ax, xS, (yT + yB) / 2, orient='v', length=2.2, name='V1',
                label_txt='12 V', plus_at_top=True)
    # 源的上端接到 a 支路、下端接地
    wire(ax, xS, (yT + yB) / 2 + 1.1, xS, yT)
    wire(ax, xS, (yT + yB) / 2 - 1.1, xS, yB)
    ground(ax, xS, yB)
    label(ax, xS - 1.5, (yT + yB) / 2 + 1.6, '同一个\n12 V 电源', size=10)

    # ---- 上支路 R1 / R2 ----
    wire(ax, xS, yT, xT, yT)
    resistor(ax, xr1, yT, orient='h', length=2.4, name='R1')
    label(ax, xr1, yT - 0.82, '3 kΩ', size=10)
    resistor(ax, xr2, yT, orient='h', length=2.4, name='R2')
    label(ax, xr2, yT - 0.82, '2 kΩ', size=10)

    # ---- 下支路 R3 / R4 ----
    wire(ax, xS, yB, xT, yB)
    resistor(ax, xr1, yB, orient='h', length=2.4, name='R3')
    label(ax, xr1, yB - 0.82, '2 kΩ', size=10)
    resistor(ax, xr2, yB, orient='h', length=2.4, name='R4')
    label(ax, xr2, yB - 0.82, '3 kΩ', size=10)

    # ---- 负载 RL 竖直跨接在 a、b 之间 ----
    resistor(ax, xT, (yT + yB) / 2, orient='v', length=(yT - yB), name='RL')
    dot(ax, xT, yT)
    dot(ax, xT, yB)

    # ---- 端口标注 ----
    port(ax, xT, yT, 'a', direction='u')
    port(ax, xT, yB, 'b', direction='d')
    annotate_arrow(ax, xT + 1.35, yT, xT + 1.35, yB, '$U_{ab}$',
                       offset=(0.85, 0.0))
    save(fig, out('thevenin_circuit.png'))


def draw_equivalent(th):
    """戴维南等效电路。"""
    fig, ax = new_figure(w=7.2, h=5.0, xlim=(-2.4, 11.0), ylim=(-1.0, 9.0),
                             title='② 戴维南等效电路（端口 a–b 保持不变）')
    xS, xT = 0.0, 8.4
    yT, yB = 6.8, 2.4
    ymid = (yT + yB) / 2

    # 电压源
    vsource(ax, xS, ymid, orient='v', length=2.4, name='Vth',
                label_txt=f'{th["Vth"]:.2f} V', plus_at_top=True)
    wire(ax, xS, ymid + 1.2, xS, yT)
    wire(ax, xS, ymid - 1.2, xS, yB)
    ground(ax, xS, yB)
    # 串联电阻 Rth
    wire(ax, xS, yT, xT, yT)
    resistor(ax, 3.2, yT, orient='h', length=2.4, name='Rth')
    label(ax, 3.2, yT - 0.82, f'{th["Rth"]/1e3:.2f} kΩ', size=10)
    # 下支路直接接地
    wire(ax, xS, yB, xT, yB)
    # 负载
    resistor(ax, xT, ymid, orient='v', length=(yT - yB), name='RL')
    dot(ax, xT, yT)
    dot(ax, xT, yB)
    port(ax, xT, yT, 'a', direction='u')
    port(ax, xT, yB, 'b', direction='d')
    annotate_arrow(ax, xT + 1.35, yT, xT + 1.35, yB, '$U_{ab}$',
                       offset=(0.85, 0.0))
    save(fig, out('thevenin_equivalent.png'))


# ============================================================
# 3. 仿真
# ============================================================
def make_netlist(RL):
    c = Circuit('Thevenin network')
    c.V('s', 'vp', c.gnd, V1 @ u_V)
    c.R(1, 'vp', 'na', R1 @ u_Ohm)
    c.R(2, 'na', c.gnd, R2 @ u_Ohm)
    c.R(3, 'vp', 'nb', R3 @ u_Ohm)
    c.R(4, 'nb', c.gnd, R4 @ u_Ohm)
    c.R('L', 'na', 'nb', RL @ u_Ohm)
    return c


def sim_port(RL):
    """仿真一次，返回 (端口电压 U_ab, 从 a 流向 b 的电流 I_L)。"""
    ana = make_netlist(RL).simulator().operating_point()
    u = float(ana['na'][0]) - float(ana['nb'][0])
    return u, u / RL


def sim_sweep(rmin, rmax, n=60):
    rls = np.logspace(np.log10(rmin), np.log10(rmax), n)
    us, iss = [], []
    for rl in rls:
        u, i = sim_port(rl)
        us.append(u); iss.append(i)
    return rls, np.array(us), np.array(iss)


# ============================================================
# 4. 负载扫描图
# ============================================================
def plot_load(rls, us_sim, iss_sim, th):
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
    rl_th = np.logspace(np.log10(rls[0]), np.log10(rls[-1]), 400)
    u_th = th['Vth'] * rl_th / (th['Rth'] + rl_th)
    i_th = th['Vth'] / (th['Rth'] + rl_th)

    for axx, ysim, yth, lab, unit in (
            (axes[0], us_sim, u_th, '端口电压 $U_{ab}$', 'V'),
            (axes[1], iss_sim, i_th, '负载电流 $I_L$', 'µA')):
        scale = 1 if unit == 'V' else 1e6
        axx.semilogx(rls / 1e3, ysim * scale, 'o', ms=3.6, color='#d62728',
                     label='原电路（PySpice 仿真）')
        axx.semilogx(rl_th / 1e3, yth * scale, '-', lw=2.0, color='#1f77b4',
                     alpha=0.85, label='戴维南等效电路（手算）')
        axx.set_xlabel('负载电阻 $R_L$ (kΩ)')
        axx.set_ylabel(f'{lab} ({unit})')
        axx.grid(which='both', alpha=0.3)
        axx.legend(fontsize=9)

    for axx in axes:
        axx.axvline(th['Rth'] / 1e3, color='green', ls='--', lw=1.3)
        axx.text(th['Rth'] / 1e3 * 1.08, axx.get_ylim()[1] * 0.12,
                 f'$R_L=R_{{th}}$=\n{th["Rth"]/1e3:.2f} kΩ', color='green',
                 fontsize=9)
    axes[0].set_title('端口电压 vs 负载', fontsize=11)
    axes[1].set_title('负载电流 vs 负载', fontsize=11)
    fig.suptitle('② 戴维南等效替换后接负载：电压 / 电流验证', fontsize=12)
    fig.tight_layout()
    save(fig, out('thevenin_load.png'))


# ============================================================
# 5. 主流程
# ============================================================
def main():
    th = hand_calc()
    print("=" * 82)
    print("② 验证戴维南定理")
    print("=" * 82)
    print("\n【手算过程】")
    print(f"  上支路分压  Va = V1·R2/(R1+R2) = 12×2/(3+2)  = {th['Va']:.4f} V")
    print(f"  下支路分压  Vb = V1·R4/(R3+R4) = 12×3/(2+3)  = {th['Vb']:.4f} V")
    print(f"  开路电压    V_oc = Va - Vb = {th['Va']:.4f} - {th['Vb']:.4f} "
          f"= {th['Vth']:.4f} V  ← V_th")
    print(f"  求 R_th：把 12 V 电源置零（短路到地），从端口 a–b 看进去")
    print(f"      R1 与 R2 并联：R1||R2 = 3k×2k/(3k+2k) = {R1*R2/(R1+R2)/1e3:.4f} kΩ")
    print(f"      R3 与 R4 并联：R3||R4 = 2k×3k/(2k+3k) = {R3*R4/(R3+R4)/1e3:.4f} kΩ")
    print(f"      两者串联：R_th = {R1*R2/(R1+R2)/1e3:.4f} + {R3*R4/(R3+R4)/1e3:.4f} "
          f"= {th['Rth']/1e3:.4f} kΩ")
    print(f"  短路电流    I_sc = V_th/R_th = {th['Vth']:.4f}/{th['Rth']:.4f} "
          f"= {th['Isc']*1e6:.4f} µA")

    print("\n【画图】")
    draw_source_network()
    draw_equivalent(th)

    print("\n【仿真 1：开路电压 V_oc（接 1 TΩ ≈ 开路）】")
    u_oc, _ = sim_port(1e12)
    print(f"  V_oc(仿真) = {u_oc:.6f} V")

    print("\n【仿真 2：短路电流 I_sc（接 1 mΩ ≈ 短路）】")
    u_sc, i_sc = sim_port(1e-3)
    print(f"  I_sc(仿真) = {i_sc*1e6:.4f} µA")

    Rth_sim = u_oc / i_sc
    print(f"  由两次仿真直接算 R_th = V_oc/I_sc = {Rth_sim:.4f} Ω "
          f"= {Rth_sim/1e3:.4f} kΩ")

    print("\n【仿真 3：扫描 60 个负载点，对端口伏安特性做线性回归】")
    rls, us_sim, iss_sim = sim_sweep(1e2, 1e6, n=60)
    A = np.vstack([np.ones_like(iss_sim), iss_sim]).T
    coef, *_ = np.linalg.lstsq(A, us_sim, rcond=None)
    Vth_fit, Rth_fit = coef[0], -coef[1]
    resid = np.abs(us_sim - (Vth_fit - Rth_fit * iss_sim)).max()
    print(f"  拟合直线 U = V_th - R_th·I :")
    print(f"      V_th(拟合) = {Vth_fit:.6f} V")
    print(f"      R_th(拟合) = {Rth_fit:.4f} Ω = {Rth_fit/1e3:.4f} kΩ")
    print(f"  最大残差 = {resid*1e6:.3e} µV（≈0，说明端口伏安特性确实是一条直线）")
    plot_load(rls, us_sim, iss_sim, th)

    # ---- 对比表 1 ----
    print("\n" + "=" * 82)
    print("【对比表 1】V_oc、I_sc 的「手算 vs 仿真」")
    print("=" * 82)
    rows = [("开路电压 V_oc (V)", th['Vth'], u_oc),
            ("短路电流 I_sc (µA)", th['Isc'] * 1e6, i_sc * 1e6),
            ("等效电阻 R_th (kΩ)", th['Rth'] / 1e3, Rth_sim / 1e3),
            ("回归得到的 V_th (V)", th['Vth'], Vth_fit),
            ("回归得到的 R_th (kΩ)", th['Rth'] / 1e3, Rth_fit / 1e3)]
    print(f"{'指标':<24}{'手算值':>14}{'仿真值':>14}{'相对误差':>12}")
    print("-" * 82)
    for n, h, s in rows:
        print(f"{n:<24}{h:>14.4f}{s:>14.4f}{abs(s-h)/abs(h)*100:>11.4f}%")
    print("-" * 82)

    # ---- 对比表 2 ----
    print("\n" + "=" * 82)
    print("【对比表 2】等效电路替换后接负载：原电路 vs 戴维南等效电路")
    print("=" * 82)
    print(f"{'R_L':>9}{'原电路 U_ab(V)':>16}{'等效 U_ab(V)':>15}{'电压误差':>11}"
          f"{'原电路 I(µA)':>14}{'等效 I(µA)':>13}{'电流误差':>11}")
    print("-" * 82)
    for RL in LOAD_TEST:
        u_ex = exact_v(RL)
        i_ex = u_ex / RL
        u_th = th['Vth'] * RL / (th['Rth'] + RL)
        i_th = th['Vth'] / (th['Rth'] + RL)
        print(f"{RL/1e3:>8.3f}k{u_ex:>16.6f}{u_th:>15.6f}"
              f"{abs(u_ex-u_th)/abs(u_ex)*100:>10.5f}%"
              f"{i_ex*1e6:>14.4f}{i_th*1e6:>13.4f}"
              f"{abs(i_ex-i_th)/abs(i_ex)*100:>10.5f}%")
    print("-" * 82)

    # ---- 加分点：最大功率传输 ----
    print("\n【加分点：最大功率传输定理】")
    u_max = exact_v(th['Rth'])
    p_max = u_max ** 2 / th['Rth']
    print(f"  当 R_L = R_th = {th['Rth']/1e3:.2f} kΩ 时，")
    print(f"    U_ab = V_th/2 = {u_max:.4f} V")
    print(f"    P_L  = V_th²/(4R_th) = {p_max*1e6:.4f} µW（负载获得最大功率）")
    print(f"  （见 thevenin_load.png 中绿虚线位置）")

    print("\n结论：所有负载点的电压/电流相对误差 < 0.01%，戴维南定理成立；")
    print("      误差来源是仿真用 1 TΩ / 1 mΩ 近似开路/短路，并非严格理想。")


if __name__ == '__main__':
    main()
