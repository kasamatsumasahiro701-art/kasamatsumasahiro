# organize_downloads

ダウンロードフォルダ内のファイルを、拡張子に応じたサブフォルダ(Images, Documents,
Videos, Audio, Archives, Installers, Spreadsheets, Presentations, Code, Others)へ
自動的に振り分ける、依存ライブラリ不要のPythonスクリプトです。Windows / macOS /
Linux で動作します。

## 使い方

```bash
# まずは dry-run で、何がどこに移動されるか確認する(実際には移動しない)
python organize_downloads.py --dry-run

# 実際に整理を実行する(デフォルトは ~/Downloads)
python organize_downloads.py

# 対象フォルダを指定する
python organize_downloads.py --path "/path/to/other/folder"

# 各カテゴリの中を、さらに更新日の年月(YYYY-MM)ごとのフォルダに分ける
python organize_downloads.py --by-date

# ダウンロード中(未完了)のファイルも対象に含める
python organize_downloads.py --include-incomplete

# 分類ルールをカスタマイズする(config.example.json を参考に作成)
python organize_downloads.py --config my_config.json
```

## 動作の仕様

- 対象フォルダ直下のファイルのみを処理します(サブフォルダの中身は再帰的に処理しません)。
- 既に整理済みのカテゴリフォルダ(Images, Documents など)や、隠しファイル(`.` で始まる
  ファイル)はスキップされます。
- `.crdownload` / `.part` / `.download` / `.tmp` など、ダウンロード中を示す拡張子の
  ファイルはデフォルトでスキップされます(`--include-incomplete` で対象に含められます)。
- 移動先に同名ファイルが既に存在する場合は、`ファイル名 (1).拡張子` のように連番を
  付けて上書きを防ぎます。
- `--config` で指定したJSONファイルの内容は、デフォルトの分類ルールに追加・上書き
  マージされます(`config.example.json` を参照)。

## 注意

- 事前に `--dry-run` で移動内容を確認することを推奨します。
- ファイルの移動は `shutil.move` で行われ、削除は行いません。
