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

---

# organize_papers(論文専用)

ダウンロードした論文PDFを、**著者_出版年_タイトル.pdf** の形式に自動リネームし、
あらかじめ指定したキーワードに応じてカテゴリフォルダ(例: MachineLearning,
Biology など)へ振り分けるスクリプトです。

### インストール

`pypdf` ライブラリが必要です。

```bash
pip install pypdf
```

分類方法は2種類あります。**どちらか一方**を指定してください。

- `--keywords keywords.json` : キーワードでカテゴリ分け(例: MachineLearning, Biology)
- `--by-author` : 著者(姓)ごとにフォルダ分け

### 使い方(著者ごとに分類する場合)

オプションを付けるだけで、PDFから抽出した著者の姓ごとにフォルダが自動で作られます
(例: `Smith/Smith_2023_Deep_Learning_for_NLP.pdf`)。

1. まず dry-run で確認する
   ```bash
   python organize_papers.py --by-author --dry-run
   ```

2. 問題なければ実行する(デフォルトは `~/Downloads` 直下のPDFが対象)
   ```bash
   python organize_papers.py --by-author
   ```

※ 著者名がPDFのメタデータから取得できない場合は `UnknownAuthor` フォルダに
入ります。共著者が複数いる場合は、1人目の著者の姓のみが使われます。同姓の
別人がいる場合は同じフォルダにまとまってしまう点にご注意ください。

### 使い方(キーワードで分類する場合)

1. `keywords.example.json` をコピーして `keywords.json` を作り、自分の研究分野に
   合わせてカテゴリ名とキーワードを編集する
   ```json
   {
     "MachineLearning": ["machine learning", "deep learning", "neural network"],
     "Biology": ["gene expression", "protein", "cell biology"]
   }
   ```
   タイトルと本文(先頭3ページ)にキーワードが含まれるかで判定し、最初に一致した
   カテゴリに分類されます。どれにも一致しない論文は `Uncategorized` フォルダへ
   入ります。

2. まず dry-run で確認する
   ```bash
   python organize_papers.py --keywords keywords.json --dry-run
   ```

3. 問題なければ実行する
   ```bash
   python organize_papers.py --keywords keywords.json
   ```

### その他のオプション

```bash
# organize_downloads.py を先に実行していて、論文PDFが Downloads/Documents に
# 移動済みの場合など、サブフォルダの中も探したいとき
python organize_papers.py --by-author --path "~/Downloads/Documents" --recursive

# リネームはせず、フォルダ分けだけ行いたいとき
python organize_papers.py --by-author --no-rename

# 「該当なし」フォルダの名前を変えたいとき(キーワード分類のみ)
python organize_papers.py --keywords keywords.json --uncategorized-folder Misc
```

### 動作の仕様と注意点

- タイトル・著者はまずPDFのメタデータから読み取り、無い/不自然な場合は本文の
  1ページ目から推測します。出版年はPDFの「作成日」ではなく、本文中に書かれた
  年号を優先して使います(作成日はダウンロードした日になっていることが多く、
  出版年としては不正確なため)。
- 推測に頼った論文は、実行結果に `[!] title/author/year guessed - please
  double-check` と表示されます。ファイル名がおかしい場合は手動で直してください。
- 著者名は主にPDFのメタデータから取得します。本文からの著者名推測は精度が
  低いため行っていません(`UnknownAuthor` になった場合は手動でリネームして
  ください)。
- 対象フォルダ直下のPDFのみが対象です(`--recursive` を付けるとサブフォルダ内も
  対象になりますが、既に分類済みのカテゴリフォルダの中は二重処理を避けるため
  スキップされます)。
- 暗号化されていたり壊れているPDFは読み込めず、その旨を表示してスキップします。
