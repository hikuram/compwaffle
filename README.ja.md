# compwaffle — Matplotlibによる端数対応ワッフルチャート

**v0.1.3（初回公開はv0.1.1、GitHubソース配布）**。配合・構成比などの数値を、角丸セルと端数セルで表すMatplotlibライブラリです。

![公開データセットを用いた比率比較表](docs/images/concrete_percent.png)

## 主な機能

- 既定は1×20セル。行数・列数、セルサイズ、縦横間隔、描画順を指定可能。
- 端数セルを正確に塗り分け、セルの外形を共有。
- `PathPatch`で四隅だけを変形。`corner_bend`は−1〜+1で、負値はへこみ、0は角落とし、約0.5523は円弧に近い形状。
- カラー・角形状・ハッチングを各カテゴリに独立して割当て可能。ハッチング色は既定で塗りつぶし色から自動調整。
- 比率を100%に正規化するモードと、量を維持する可変長モード。
- 任意の成分（複数も可）を基準量100とする換算、密度を与えた質量→体積換算。
- 凡例、スケール、コメント、物性列付きの比較表。交互行背景は`show_stripes=False`で無効化可能。
- **v0.1.3：** CSVからテンプレートなしでPython in Excel用XLSXを生成（最大16成分・256配合）。

## インストールと確認

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python examples/concrete_slump.py
python examples/shape_styles.py
```

## CSVからPython in Excel対応ブックを生成

```bash
python -m pip install -e '.[excel]'
compwaffle-excel examples/python_in_excel/example_generic_7.csv -o waffle.xlsx
```

`table`シートへCSVの全列・全行をコピーし、`waffle`シートに設定、凡例、PYセル、評価値列を生成します。外部XLSXテンプレートは不要です。配合として可視化する列範囲と評価値列はPython側で明示的に指定します。

```python
from dataclasses import replace
from compwaffle.excel import ExcelSettings, build_excel_workbook

base = ExcelSettings()
settings = replace(base, composition_range="B2:Q257",
                   evaluation_columns=("R", "S", "T"),
                   options={**base.options, "hatch_tone_shift": -30})
build_excel_workbook("input.csv", "output.xlsx", settings)
```

Excel用の`lxml`はオプション依存です。出力したブックには描画コードが内蔵されますが、PYセルの実行にはMicrosoft 365の対応環境が必要です。Pythonコードや参照数値はクラウドで処理されます。詳細は[Excel向け手順（英語）](docs/EXCEL.md)を参照してください。

## Python in Excelの再計算と結果の持ち帰り

生成された`waffle`シートは、継続的な配合管理ではなく**視覚化作業用**として利用することを推奨します。配合値や設定の変更によってPYセルが再計算され、配合数が多い場合は処理に時間がかかります。

元の配合管理ブックを維持し、CSVからcompwaffleブックを生成して画像を完成させたら、**完成したワッフルだけ**を元ブックへ静的画像として持ち帰る運用が適しています。Python出力を「Excel値」にしたセルから「値の貼り付け」を試し、貼り付け先にPY式が残っていないことを確認してください。画像が維持されない場合は「図としてコピー／図として貼り付け」を利用します。PYセルの数式自体を作業用ブックにコピーすることは推奨しません。

Python in Excelの手動／部分計算モードには追加ライセンスが必要なため、生成ブックは標準の**自動計算**を維持します。詳細は[Excel向け手順（英語）](docs/EXCEL.md#recalculation-and-transferring-finished-charts)を参照してください。

## 基本例

```python
from compwaffle import waffle, parts_per_reference

values = {"Category A": 72.5, "Category B": 17.5, "Category C": 10}
fig, ax = waffle(values, columns=20, style="rounded", show_scale=True)
fig.savefig("waffle.svg")

amounts = {"Category A": 100, "Category B": 20, "Category C": 2.5}
parts = parts_per_reference(amounts, "Category A")
fig, ax = waffle(parts, mode="absolute", unit="parts",
                 value_per_cell=5, columns="auto")
fig.savefig("absolute.svg")
```

`mode="percent"`では合計100%に正規化します。`mode="absolute"`では元の量を保ち、`value_per_cell`で1セルの量を指定します。`parts_per_reference()`は基準成分の合計を100とする汎用変換です。`unit`は表示ラベルであり、単位換算を自動実行するものではありません。

## 色・形状・ハッチング

```python
from compwaffle import CornerShape, WaffleStyle, waffle_table

style = WaffleStyle(
    corner_span=0.10,
    color_map={"Category A": "#619BCE", "Category B": "#78A68C"},
    shape_map={"Category A": (0.10, 0.55),
               "Category B": CornerShape(0.10, -0.8)},
    hatch_map={"Category A": None, "Category B": "//"},
    hatch_tone_shift=-30,  # ハッチングの明暗調整
)
records = [
    {"label": "01", "composition": {"Category A": 75, "Category B": 25}},
    {"label": "02", "composition": {"Category A": 72.5, "Category B": 27.5}},
]
fig, ax = waffle_table(records, style=style, show_stripes=False)
```

個別形状は単一カテゴリの完全セルに適用し、端数・混在セルには共通マスクを使います。角の変形範囲を小さくすると面積差を抑えられますが、厳密に等面積ではありません。

ハッチング色は塗りつぶし色ごとに算出し、`hatch_tone_shift=-30`（RGBで黒へ30%寄せる）が既定値です。指定範囲は-100（黒）～+100（白）、0で元の色と一致します。知覚上の輝度ではなくRGBの明暗調整です。`hatch_color="#263445"`など明示した色を優先できます。Python in Excelの生成ブックでは`waffle!B15`で同じ明暗調整を指定でき、凡例にも適用します。

![形状とハッチングによるグレースケール表示](docs/images/shape_grayscale_preview.png)

## 公開データセット

同梱のUCI *Concrete Slump Test*（103件、原材料7種、評価値3種）で、比率型・基準量100に対する可変長型を検証できます。材料の数値と評価値は別列として扱います。

ソースとライセンス: I-Cheng Yeh (2007), [Concrete Slump Test](https://doi.org/10.24432/C5FG7D)、CC BY 4.0。プログラム本体はMITライセンスです。

[API詳細](docs/API.md) / [Python in Excelでの利用方法](docs/EXCEL.md)
