# MetaTune

## 概要
音楽ファイル(.mp3)のメタデータを編集できるGUIアプリ。  
編集できるメタデータは以下の通り
- タイトル名
- アルバム名
- アーティスト名
- カバー画像

## 事前準備
このリポジトリをクローンしてください。  
その後、クローンしたディレクトリで以下のコマンドを実行し必要なモジュールをインストールしてください。  
  
`pip install -r requirements.txt`

## 使い方
1. アプリを起動  
`python main.py`

1. "Select MP3 File"で音楽ファイルを選択
   
1. メタデータを編集  
   カバー画像の指定方法(2通り)
   - ローカルの画像ファイルを指定して更新  
     "Select Cover Image (Local)"で画像ファイル(.jpg, .jpeg, .png)を指定
   - 画像のURLを指定して更新  
     URLを入力し"Download Cover Image from URL"で画像を指定
     
1. "Save Metadata"でメタデータを保存

## 注意
タイトル名を変更するとファイル名もタイトル名に変更されます。
