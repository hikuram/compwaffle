# Python in Excel（任意の組成データを1行1画像で表示）

Python in Excelにはローカルにインストールした`compwaffle`を直接読み込めないため、`examples/python_in_excel/`の**移植版描画コード**をExcelのPYセルへ登録します。標準のライブラリをそのままインポートする方法ではありません。

1. Excelで、元データの数値列を`table!B:H`（2行目以降）に置き、`waffle`シートに設定欄を作る（材料名などの文字列はExcel側で管理）。
2. `waffle!K1` に「数式 → Pythonの挿入」で`engine_part1.py`、`waffle!K15`に`engine_part2.py`を登録。各コードはExcelの数式文字数制限を考慮して分割済み。
3. `waffle!B20` に`row_example.py.txt`をPYコードとして登録し、**Python出力 → Excel値**に変更。画像をセル内に表示して、B21以降へ**PYセル自体をコピー**する。
4. 任意の凡例は`waffle!B17`へ`swatch_example.py.txt`を登録し、右方向にコピーする。

**参照の固定：** 行ごとに変わる数値データは`table!$B2:$H2`（列固定／行相対）。スタイル設定は`waffle!$B$7:$H$7`などの絶対参照。凡例だけは`waffle!B$4:B$5`のように列相対／行固定とする。

**設定例：** 色の16進表示をB3に置いた場合、B7に`=HEX2DEC(RIGHT(B3,6))`を指定し、右へコピーします。ハッチ番号は0=なし、2=`//`、12=`..`、14=`xx`など（`engine_part1.py`の`_CW_HATCHES`の順序）。`K2:K13`の既定値の例は`0, 20, 1, 0.78, 0.12, 0.18, 100, 0.10, 0.55, 0, 32, -30`です。

**設定範囲：** `B4:H5`は角の変形、`B7:H7`は数値化したRGB、`B8:H8`はハッチ番号、`B14:H14`は基準量の重み、`K2:K13`は表示モード・セル数・寸法・スケール・ハッチング明暗調整の数値です。実際のカテゴリ数と参照範囲は同数に揃えてください。`K2` は0=比率、1=絶対量、2=任意基準量100への換算です。`K13` は「ハッチング明暗調整」（`hatch_tone_shift`）で、-100（黒）～+100（白）、既定値-30です。RGB値を黒または白へ補間する方式です。塗りつぶし色ごとに計算し、凡例も同じ色になります。旧来の11項目（`K2:K12`）を渡した場合も内部で-30を使いますが、新規設定では`K2:K13`を参照してください。

**クラウド処理の注意：** Python in ExcelはMicrosoft Cloudで実行されます。サンプルでは`xl()`の参照を数値範囲だけに限定していますが、**Pythonコードと参照された数値はクラウドに送信されます**。機密データをクラウド処理できない場合は通常のローカルPython版を使用してください。ExcelのPYセルは必ずExcel上で作成し、外部のxlsx生成ライブラリからPY専用の内部構造を書き換えないでください。

Microsoft公式: [Pythonの挿入](https://support.microsoft.com/ja-jp/excel/python/get-started-with-python-in-excel) / [グラフをセル内に表示](https://support.microsoft.com/ja-jp/excel/python/create-plots-and-charts-with-python-in-excel)。
