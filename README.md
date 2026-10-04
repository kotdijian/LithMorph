# LithMorph

**姿勢正規化済みの石器3Dモデルを対象とする、表面ベースの形態解析プロジェクトです。**

基本入力は[ArtefactsOrthoMaker](https://github.com/kotdijian/ArtefactsOrthoMaker)が出力する三角形メッシュPLYです。ボクセル化せず、XY平面形態とXZ／YZ連続断面から解析します。既に適用された姿勢Transformを再適用しません。

現在はdev2の計算コアを継承し、平面形態の面積・周長・重心・幅プロファイル・最大幅位置と、断面別の面積・周長・重心・輪郭トポロジーを実装しています。形状比に応じた断面数の配分、CSV／JSON出力、QA、ベンチマークも含みます。

Surface Enhancement Labは共通手法の継承用としてexperimental/に収録しています。統合GUIと、対称性・楕円率・鋭さ・ねじれ等のオプション解析は今後開発します。

土器の容量・器軸・断面解析は[MorphPot](https://github.com/kotdijian/MorphPot)で開発します。

実装範囲、モジュール構成、開発計画、検証結果は[DevelopmentReport](DevelopmentReport.md)を参照してください。移管元は[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json)に記録しています。

