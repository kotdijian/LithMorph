# LithMorph DevelopmentReport

更新日：2026-10-05 JST  
状態：dev2計算コア継承＋単位受け渡し改善

## 1. 開発方針
基本入力はOrthoMaker出力のnormalized triangular PLY。姿勢Transformを再適用しない。石器は表面メッシュで解析し、voxel化しない。

座標軸は全ツール共通に固定せず、系列・処理ごとに定義する。現在の計算コアの標準設定はX=幅、Y=長さ、Z=厚さ。任意軸の指定とSurface投影adapterは今後追加する。

## 2. 移管元・今回の変更
- ArtefactsOrthoMaker commit 5d772de098c41a056580d922b1f81013b803ad5eに追加されたLithMorph_v0_1_0_dev2.zipを展開し、Python package、tests、self_test、benchmarkを移管。
- ZIPに含まれた__pycache__やpytest cacheは除外。
- LithMorph.pyを入口として追加。analyze.pyも保持。
- metadataの単位解決をlithmorph/asset_metadata.pyへ分離し、同名asset JSONと従来transform.jsonを読み込む。
- 既定出力を<PLY folder>/lithic_surface_analysis/<stem>/へ変更し、同フォルダの複数資料の結果衝突を減らす。--outで明示指定も可能。同じ入力の再実行は従来どおり同じ出力を更新する。
- Surface Enhancement Lab v0.7.3をexperimental/に継承用として収録。統合GUIへの接続は今後行う。
- OrthoMakerのMainWindowやpose_coreを必須importしない。

## 3. 実装済み機能
| モジュール | 実装 |
|---|---|
| lithmorph/planform.py | XY外包絡、面積・周長・重心、幅／中心線profile、最大幅位置、raw／smooth最大幅 |
| lithmorph/sampling.py | Sparse9 / Low25 / Default49 / High99、bbox形状比によるXZ／YZ断面数配分 |
| lithmorph/sections.py | triangle-plane交差、連続XZ／YZ断面、再利用slicer |
| lithmorph/contours.py | 輪郭連結、成分、閉／開曲線、既定256点の再標本化 |
| lithmorph/models.py | 断面別の面積・周長・面積重心・bbox・開曲線長・topology等 |
| lithmorph/io.py | normalized PLY読込、QA、SHA256 |
| lithmorph/asset_metadata.py | 単位・対応asset JSONのhash検証、旧metadata互換 |
| lithmorph/analysis.py / export.py | 基本解析pipeline、CSV／JSON、計算時間・条件 |
| lithmorph/optional/ | オプションanalyzer登録インターフェース。具体指標は未実装 |
| benchmark.py | 4preset比較、断面積分の診断体積誤差 |
| experimental/surface_enhancement_lab.py | Base／Top、線状性・連続性、合成、bakeの継承用Lab |

dev2平面形態は1001本のdense scanlineによる左右外包絡を基本とし、serial section数に依存しない。triangleの投影polygon unionを使うdev1方式へ戻していない。最大幅位置はYmin→Ymaxの0–100%。99%plateau基準は採用しない。

平面外包絡は内部孔や同じYに分離領域がある外形の厳密polygon unionではない。無効scanlineの補間・平滑化の影響をQAする必要がある。

断面位置はk/(N+1)で0%／100%接平面を除く。Y>2XならXZ=N／YZ≈N/2、Y<X/2なら逆、中間は両方N。約半数でも奇数に保ち50%断面を含む。開曲線は保存し強制閉合しない。

出力：
- summary.json、qa.json
- planform_profile.csv、planform_outline.csv
- section_summary.csv、section_points.csv

## 4. 入出力とメタデータ
同名<stem>.asset.jsonのschema_version=1.0、triangle_mesh、SHA-256、coordinates.unit／unit_to_mmを検証する。明示--unitとasset JSONが矛盾する場合も停止する。

asset JSONがなければ明示unitを使い、autoでは隣接transform.jsonのsource単位を読む。旧source.sha256はraw入力なのでnormalized PLYとの比較に使わない。旧metadataのcoordinate_values_rescaled=trueはauto解決しない。

単位不明なら明示指定を求める。行列を再適用せず、座標値も読込時にmmへ一律変換しない。計測列はnative値とmm換算値を区別する。

完全なmetadata schema／生成／フレーム・変換履歴の出力、任意軸、BagItはまだ未実装。

## 5. 開発者用実行例
READMEは概要のみとする。
~~~bash
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python LithMorph.py /path/stone001_rev.ply --preset Default
python LithMorph.py /path/stone001_rev.ply --unit mm --preset Sparse
python benchmark.py /path/stone001_rev.ply --out /path/benchmark
~~~
Windowsはvenv\\Scripts\\Activate.ps1で有効化。metadataなしでは--unitが必要。

requirements-dev.txtはpytest、requirements-surface.txtはNumba／PySide6を含む実験Labの追加依存。通常の形態解析にQt／VTKは不要。

Surface Labはmm前提の既存実験UI。実験Labの自動単位換算や統合metadata読込は未接続。手法は土器系と共有できるが、投影方向・軸の意味は石器系で設定する。

## 6. 今回の検証
環境：Python3.12、NumPy2.5.3、SciPy1.17.0、Trimesh5.1.1、Pillow12.3.0、NetworkX3.7。

- pytest：既存6＋metadata3＝9 passed。
- self_test.py：passed。
- 全Python compileall。
- 人工直方体PLYでLithMorph.pyを実行し、自動単位解決と資料別出力を確認。面積4000 mm²、最大幅40 mm、最大幅位置50%、SparseはXZ9／YZ5。
- 今回は250万face実資料benchmarkを再実行していない。過去性能値を新環境での検証値として扱わない。
- Surface LabのGUI／render／bakeは今回実機回帰していない。

## 7. 今後の予定
1. metadata生成・schema、フレーム／軸設定、単位同値性・ファイル対応を整備。
2. 実資料でplanform外包絡・最大幅・topologyとsampling収束を検証。
3. Surface計算とUIを分離し、石器用投影設定から利用する。
4. geometry coreと性能を確認してからGUIを追加。
5. 登録型optional analyzerへ平面楕円率／鋭さ、平面・断面対称性、Y軸ねじれ、YZ直線性／曲率を追加。
6. CI、結果のschema版管理、共通数値処理のpackage化を検討。

土器の容量はMorphPot、姿勢正規化はOrthoMakerに保持。瓦は将来の別サブプロジェクト。

## 8. 出典・ライセンス
新repoのMIT LICENSEを保持。移管元・各ファイルのhashはSOURCE_PROVENANCE.jsonに記録。実験Labの由来はTHIRD_PARTY_NOTICES.mdに記載。

