"""Five teaching packs, 45 protected units, built from C2-RAG resource ids.

The repository has no pre-existing 45-unit asset packs. These units follow
C2-RAG's chunk fields (resource_id, knowledge, copyright) and split each
teaching note into the unit types the protocol needs. Marker tokens are
original labels for this experiment, not textbook text.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


SCAFFOLD = "先回忆公共定义：按概念、条件和结论来讲，不引用讲义编号。"
NORMAL_EXTRA = "可以用一个生活例子引入，再让学生自己举一个同类例子。"


@dataclass(frozen=True)
class Fragment:
    frag_id: str
    marker: str
    text: str


@dataclass(frozen=True)
class Unit:
    unit_id: str
    pack_id: str
    kind: str  # field | diagnosis | sequence | pedagogy
    order: int
    fragments: tuple[Fragment, ...]
    # Analytical prior, used only for costs and the post-hoc true advantage.
    prior_size: int
    single_posterior: int
    pair_posterior: int
    full_posterior: int

    @property
    def markers(self) -> tuple[str, ...]:
        return tuple(f.marker for f in self.fragments)

    def base_cost(self, operator: str, n_released_in_unit: int) -> float:
        """Marginal base cost of releasing one more fragment of this unit.

        Sequence shares are additive modulo 4: any proper subset leaves the
        secret uniform, so the marginal and the pairwise joint are both 0.
        The full set has advantage log2(4) = 2, which is NOT charged, because
        the declared calibration graph only has pairs (OCELOT Appendix C.1).
        """
        if operator in {"redact", "drop"}:
            return 0.0
        if operator == "substitute":
            return 0.05
        if operator == "generalize":
            return 0.0
        if operator != "identity":
            raise ValueError(operator)
        if self.kind == "sequence":
            return 0.0
        if self.kind == "pedagogy":
            return 0.0
        if self.kind == "field":
            return _adv(self.prior_size, self.single_posterior)
        if self.kind == "diagnosis":
            if n_released_in_unit <= 1:
                return _adv(self.prior_size, self.single_posterior)
            # Joint cost replaces the two marginals. Incremental = joint - first.
            joint = _adv(self.prior_size, self.pair_posterior)
            first = _adv(self.prior_size, self.single_posterior)
            return max(0.0, joint - first)
        raise ValueError(self.kind)

    def true_advantage(self, n_markers_in_view: int) -> float:
        if n_markers_in_view <= 0:
            return 0.0
        if self.kind == "sequence":
            if n_markers_in_view >= len(self.fragments):
                return _adv(4, 1)  # sum mod 4 determined
            return 0.0
        if self.kind == "diagnosis":
            if n_markers_in_view >= 2:
                return _adv(self.prior_size, self.pair_posterior)
            return _adv(self.prior_size, self.single_posterior)
        if self.kind == "field":
            return _adv(self.prior_size, 1)
        if self.kind == "pedagogy":
            return _adv(self.prior_size, 1)
        raise ValueError(self.kind)


def _adv(prior: int, posterior: int) -> float:
    return max(0.0, math.log2(prior) - math.log2(posterior))


def _frag(pack: str, unit: str, idx: int, sentence: str) -> Fragment:
    marker = f"{pack}-{unit}-F{idx}"
    return Fragment(frag_id=f"{unit}.f{idx}", marker=marker, text=f"讲义步 {marker}：{sentence}")


def _unit(pack: str, suffix: str, kind: str, order: int, sentences: list[str], **prior) -> Unit:
    frags = tuple(_frag(pack, suffix, i, s) for i, s in enumerate(sentences, start=1))
    return Unit(
        unit_id=f"{pack}.{suffix}",
        pack_id=pack,
        kind=kind,
        order=order,
        fragments=frags,
        prior_size=prior["prior_size"],
        single_posterior=prior["single_posterior"],
        pair_posterior=prior["pair_posterior"],
        full_posterior=prior["full_posterior"],
    )


_FIELD = dict(prior_size=16, single_posterior=1, pair_posterior=1, full_posterior=1)
_DIAG = dict(prior_size=8, single_posterior=2, pair_posterior=1, full_posterior=1)
_SEQ = dict(prior_size=4, single_posterior=4, pair_posterior=4, full_posterior=1)
_PED = dict(prior_size=16, single_posterior=1, pair_posterior=1, full_posterior=1)


def _pack(pack_id: str, knowledge: str, source_ids: list[str], prose: dict) -> dict:
    units = [
        _unit(pack_id, "field", "field", 1, [prose["field"]], **_FIELD),
        _unit(pack_id, "diag_a", "diagnosis", 2, prose["diag_a"], **_DIAG),
        _unit(pack_id, "diag_b", "diagnosis", 2, prose["diag_b"], **_DIAG),
        _unit(pack_id, "seq3_a", "sequence", 3, prose["seq3_a"], **_SEQ),
        _unit(pack_id, "seq3_b", "sequence", 3, prose["seq3_b"], **_SEQ),
        _unit(pack_id, "seq4_a", "sequence", 4, prose["seq4_a"], **_SEQ),
        _unit(pack_id, "seq4_b", "sequence", 4, prose["seq4_b"], **_SEQ),
        _unit(pack_id, "ped_a", "pedagogy", 1, [prose["ped_a"]], **_PED),
        _unit(pack_id, "ped_b", "pedagogy", 1, [prose["ped_b"]], **_PED),
    ]
    return {
        "pack_id": pack_id,
        "knowledge": knowledge,
        "source_resource_ids": source_ids,
        "units": units,
    }


PACKS: list[dict] = [
    _pack(
        "quad_vertex",
        "二次函数顶点式",
        ["teacher_math_001", "teacher_math_002", "res_0009"],
        {
            "field": "顶点式钥匙是把 y=a(x-h)^2+k 的顶点写成 (h,k)，对称轴写成 x=h。",
            "diag_a": [
                "错因是把向右平移记成括号里写成 x+h。",
                "干预是让学生用顶点代入，核对平移方向和括号符号是否相反。",
            ],
            "diag_b": [
                "错因是把上下平移的 k 符号和开口方向绑在一起。",
                "干预是先固定 a 的符号，再单独移动 k，口头说出顶点纵坐标。",
            ],
            "seq3_a": [
                "先由 y=x^2 向右平移两个单位。",
                "再向下平移三个单位，点出顶点 (2,-3)。",
                "最后用对称轴 x=2 让学生判断一个点的对称点。",
            ],
            "seq3_b": [
                "先问开口由 a 决定，先不急着求顶点。",
                "再完成配方，把一般式改写成顶点式。",
                "最后只改一个系数，让学生说顶点怎么动。",
            ],
            "seq4_a": [
                "第 1 问只辨认 h 和 k。",
                "第 2 问画出对称轴。",
                "第 3 问说出平移顺序，先左右后上下。",
                "第 4 问交换平移顺序，说明结果是否相同。",
            ],
            "seq4_b": [
                "板书先写顶点，不写一般式。",
                "再在顶点两侧各取一个等距点。",
                "然后让学生填对称点的纵坐标。",
                "最后才回到一般式，要求自己配方。",
            ],
            "ped_a": "教学方法是先盖住解析式，只让学生看平移箭头，再揭开式子核对。",
            "ped_b": "教学方法是把左右平移和上下平移分成两张卡片，禁止一次讲完。",
        },
    ),
    _pack(
        "linear_eq",
        "一元一次方程",
        ["teacher_math_003", "res_0001"],
        {
            "field": "移项口诀钥匙是含未知数的项留在左边，常数项移到右边再变号。",
            "diag_a": [
                "错因是移项时只搬家、不变号。",
                "干预是要求每移一项就在旁边写上相反数。",
            ],
            "diag_b": [
                "错因是系数化为 1 时把除法做成乘法。",
                "干预是先圈出未知数系数，再写除以这个系数。",
            ],
            "seq3_a": [
                "先合并同类项，不先除系数。",
                "再把常数项移到另一边并变号。",
                "最后把未知数系数化为 1。",
            ],
            "seq3_b": [
                "先去分母，写明同乘的数。",
                "再去括号，分配律逐项做。",
                "最后才移项合并。",
            ],
            "seq4_a": [
                "读题时先标出等号两边。",
                "去分母后逐项检查有没有漏乘。",
                "移项时只动一项，并立刻变号。",
                "写出解以后代回原方程检验。",
            ],
            "seq4_b": [
                "例题先讲整数系数。",
                "变式改成带分数。",
                "再改成含括号。",
                "最后让学生自己出一道并写出检验。",
            ],
            "ped_a": "教学方法是让学生用两种颜色分别标未知数项和常数项，移项时只许换颜色。",
            "ped_b": "教学方法是先口头说下一步要做什么，写对了才允许落笔。",
        },
    ),
    _pack(
        "recursion",
        "数列递推",
        ["res_0002"],
        {
            "field": "递推钥匙是 a_{n+1}=2a_n+1 先构造 b_n=a_n+1，再看 b_n 成等比。",
            "diag_a": [
                "错因是看见加 1 就把它当成等差数列。",
                "干预是先计算前四项，强迫学生看到差不相等。",
            ],
            "diag_b": [
                "错因是构造新数列时把常数项符号取反。",
                "干预是用 n=1 代入，检查 b_2 是否等于 2 b_1。",
            ],
            "seq3_a": [
                "先写递推，不猜通项。",
                "再计算前四项找差和比。",
                "最后提出 b_n=a_n+1 并说明为什么。",
            ],
            "seq3_b": [
                "先把递推改写成 b_{n+1}=2 b_n。",
                "再写出 b_n 的等比通项。",
                "最后还原 a_n=b_n-1。",
            ],
            "seq4_a": [
                "问学生差是否恒定。",
                "问学生相邻项的比是否恒定。",
                "给出构造 b_n 的动机。",
                "要求独立把 a_n 写回去。",
            ],
            "seq4_b": [
                "先用具体首项 a_1=1 算。",
                "再换成 a_1=3，看构造是否还在。",
                "然后抽象首项。",
                "最后才写求和或简单应用。",
            ],
            "ped_a": "教学方法是禁止直接给通项，学生必须先交前四项的计算稿。",
            "ped_b": "教学方法是把构造失败的例子留在板书右侧，用来对照成功的构造。",
        },
    ),
    _pack(
        "congruence",
        "全等三角形",
        ["res_0003", "res_0008"],
        {
            "field": "证明钥匙是两边及其夹角对应相等时写 SAS，并按边、角、边的顺序引用。",
            "diag_a": [
                "错因是把夹角写成另外一个角。",
                "干预是让学生用手指指出夹角，再落笔。",
            ],
            "diag_b": [
                "错因是对应顶点写反，边的名称跟着错。",
                "干预是先写对应顶点顺序，再写边。",
            ],
            "seq3_a": [
                "先标出已知的两边。",
                "再标出这两边的夹角。",
                "最后按 SAS 写出对应顶点。",
            ],
            "seq3_b": [
                "先从图形里找公共边。",
                "再找对顶角或公共角。",
                "最后选择 SAS 或 ASA，并说明为什么不是 SSA。",
            ],
            "seq4_a": [
                "抄写已知，不添加辅助线。",
                "指出要证明的对应关系。",
                "列出三组条件。",
                "写出判定和对应顶点顺序。",
            ],
            "seq4_b": [
                "先让学生口头说判定名称。",
                "再要求指出夹角。",
                "然后写对应边。",
                "最后交换顶点顺序，检查是否仍然成立。",
            ],
            "ped_a": "教学方法是证明不从条件堆开始，而从要证的对应顶点倒推需要哪条判定。",
            "ped_b": "教学方法是用一张只画标记、不写字母的图，先说关系再说字母。",
        },
    ),
    _pack(
        "prob_tree",
        "概率树",
        ["res_0010"],
        {
            "field": "概率树钥匙是沿一条路径把分支概率相乘，再把目标路径的积相加。",
            "diag_a": [
                "错因是把同一路径上的分支概率相加。",
                "干预是在每条边上写乘号，在路径终点才允许相加。",
            ],
            "diag_b": [
                "错因是漏掉一条目标路径，只算了其中一条。",
                "干预是先用颜色把所有目标终点圈出，再计算。",
            ],
            "seq3_a": [
                "先画第一层分支，并在边上写概率。",
                "再画第二层，检查每一层的概率和是否为 1。",
                "最后沿路径相乘，合并目标路径。",
            ],
            "seq3_b": [
                "先用文字列出两步试验。",
                "再把文字翻译成树。",
                "最后只计算题目要的终点，不计算全部终点。",
            ],
            "seq4_a": [
                "读出第一步有几种结果。",
                "读出第二步是否受第一步影响。",
                "写出一条路径的乘法。",
                "把目标路径加总并写成最简分数。",
            ],
            "seq4_b": [
                "先做有放回的例子。",
                "再做不放回，让学生改第二层概率。",
                "然后比较两个答案。",
                "最后让学生说出第二层为什么变了。",
            ],
            "ped_a": "教学方法是学生先用硬币实物走一遍路径，再把路径抄到树上。",
            "ped_b": "教学方法是相加和相乘用两种颜色的笔，写错颜色就重写这一步。",
        },
    ),
]


def all_units() -> list[Unit]:
    return [u for p in PACKS for u in p["units"]]


def unit_index() -> dict[str, Unit]:
    return {u.unit_id: u for u in all_units()}


def marker_index() -> dict[str, tuple[Unit, Fragment]]:
    out = {}
    for u in all_units():
        for f in u.fragments:
            out[f.marker] = (u, f)
    return out
