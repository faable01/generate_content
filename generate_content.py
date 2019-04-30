import re
import requests
from bs4 import BeautifulSoup
import datetime
from janome.tokenizer import Tokenizer
import random
import markovify
import ssl
from concurrent.futures import ThreadPoolExecutor
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from readability.readability import Document
from extractcontent3 import ExtractContent
import re

# InsecureRequestWarningを非表示にする
urllib3.disable_warnings(InsecureRequestWarning)

# tokennizer作成
t = Tokenizer()

# ユーザ入力 >>> シャッフル元ページの取得件数
number_of_pages = int(input('シャッフル元となるページの取得件数を入力してください >>> '))

# ユーザ入力 >>> 除外するドメインのリスト
user_input = input('除外するドメインを指定してください（スペースを空けて複数指定可能） >>> ').strip() or None
exclusion_domain_list = user_input and user_input.split() or []

# 検索エンジンの指定
search_engine = 0
while not search_engine in (1, 2, 3):
  search_engine = int(input('検索エンジンを選択してください。 1. Google, 2. Yahoo!, 3. Bing（1, 2, 3のどれかを押してください） >>> '))

# ユーザ入力 >>> 検索キーワード
search_keyword = '+'.join(input('検索キーワードを入力してください >>> ').split())

# デフォルトの削除ドメイン
default_exclusion_domain_list = ["https://www.amazon.co.jp/", "https://www.rakuten.co.jp/", "https://kakaku.com/", "https://twitter.com/", "https://www.instagram.com/", "https://www.cosme.net/", "https://beauty.hotpepper.jp/", "https://search.rakuten.co.jp/"]
exclusion_domain_list.extend(default_exclusion_domain_list)

# 必須KW
must_keyword = input('必須キーワードを入力してください >>> ')


# ______________________________________________________________________________________________
#
# ファイル操作系
# -----------------

def write_next_line(filename, str):
  with open(filename, mode="a") as f:
    f.write("\n")
    f.write(str)

def write(filename, str):
  with open(filename, mode="w", encoding="UTF-8") as f:
    f.write(str)

def read(filename):
  with open(filename) as f:
    return f.read()

def read_lines_as_list(filename):
  with open(filename) as f:
    return f.readlines()

# ______________________________________________________________________________________________
#
# 文字列操作系
# -----------------

# 指定した品詞の文字列を取得するメソッド
def getSurfaceOf(token_list, part_of_speech):
  return [token.surface for token in token_list if token.part_of_speech.startswith(part_of_speech)]

# 第一引数の文字列の【名詞,一般】トークンを、第二引数の入れ替え候補リストの中からランダムに選ばれた単語と入れ替える
def swapNoun(target, candidate_list_to_replace):
  # 分かち書き
  wakati = [token.surface for token in t.tokenize(target)]
  # 分かち書きに対応した品詞リスト
  part_of_speech_list = [
      token.part_of_speech for token in t.tokenize(target)]
  # 名詞,一般のインデックスを取得
  target_index_list = [i for i, x in enumerate(
      part_of_speech_list) if x.startswith('名詞,一般')]
  # 名詞,一般を、事前に取得した名詞,一般リストの中からランダムに選んだものと入れ替える
  for i in target_index_list:
    wakati[i] = len(candidate_list_to_replace) and random.choice(
        candidate_list_to_replace) or print('[candidate_list_to_replace()] is nothing.')
  # 入れ替えた結果を返却する
  return "".join(wakati)

# 文字列に特定のキーワードが入っているかを確認する関数
def has_kw(target_kw, target_str):
  return target_kw in target_str

# 文字列の配列の要素を改行で結合する
def create_str_lines(str_list):
  return "\n".join(str_list)

# 対象の文字列を分ち書きする
def create_wakati_list(target: str) -> list:
  return t.tokenize(target, wakati=True)

# 分ち書きしたリストを半角スペースで繋げた文字列を返す
def create_wakati_line(wakati_list: list) -> str:
  return " ".join(wakati_list)

# 文字列を分ち書きして半角スペースで区切った文字列を返す
def write_wakati(target: str) -> str:
  return create_wakati_line(create_wakati_list(target))

# エスケープを削除する（二重バックスラッシュを一重にする）
def delete_escape(target: str) -> str:
  return target.replace("¥¥", "¥")

# HTMLタグを正規表現で削除する
def delete_tag(html: str) -> str:
  p = re.compile(r"<[^>]*?>")
  return p.sub("", html)

# 空白削除
def delete_empty(target: str) -> str:
  return target.replace(" ", "")

# ______________________________________________________________________________________________
#
# 見た目変更系
# -----------------

# コンソール出力時の色を付与するクラス
class pycolor:
  BLACK = '\033[30m'
  RED = '\033[31m'
  GREEN = '\033[32m'
  YELLOW = '\033[33m'
  BLUE = '\033[34m'
  PURPLE = '\033[35m'
  CYAN = '\033[36m'
  WHITE = '\033[37m'
  END = '\033[0m'
  BOLD = '\038[1m'
  UNDERLINE = '\033[4m'
  INVISIBLE = '\033[08m'
  REVERCE = '\033[07m'
  
  @classmethod
  def paint(self, target: str, color: str) -> str:
    return f"{color}{target}{pycolor.END}"
  
  @classmethod
  def print_red(self, target: str):
    print(pycolor.paint(target, pycolor.RED))
  
  @classmethod
  def print_green(self, target: str):
    print(pycolor.paint(target, pycolor.GREEN))
  
  @classmethod
  def print_yellow(self, target: str):
    print(pycolor.paint(target, pycolor.YELLOW))
  
  @classmethod
  def print_blue(self, target: str):
    print(pycolor.paint(target, pycolor.BLUE))


# ______________________________________________________________________________________________
#
# 検索系
# -----------------

# Googleで検索する（キーワードとstart位置を指定してGoogle検索結果のURLのタグのリストを返却する関数）
def get_url_tag_list(keyword, start):
  url = 'https://www.google.co.jp/search'
  headers = {
      "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"}
  # URLパラメータ作成：tbm: 検索パターンの指定, start: 検索をスタートする開始位置
  #（'+'がエンコードされる件の参照：https://www.monotalk.xyz/blog/nonencoded-querystring-on-python-requests/）
  search_params = {'q': keyword, 'start': start}
  p_str = "&".join("%s=%s" % (k, v) for k, v in search_params.items())
  # HTTP通信と結果の取得・パース
  search_res = requests.get(url, params=p_str, headers=headers)
  search_soup = BeautifulSoup(search_res.text, 'html.parser')
  # 検索結果一覧
  url_tag_list = search_soup.select('.C8nzq.BmP5tf:not(.d5oMvf)')
  return url_tag_list

# Yahoo!で検索する
def search_by_yahoo(keyword, start):
  url = 'https://search.yahoo.co.jp/search'
  headers = {
      "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"}
  search_params = {"ei": "UTF-8", "fr": "top_smf",
                   "meta": "vc=", "p": keyword, "b": start or 1}
  p_str = "&".join("%s=%s" % (k, v) for k, v in search_params.items())
  search_res = requests.get(url, params=p_str, headers=headers)
  search_soup = BeautifulSoup(search_res.text, 'html.parser')
  base_list = search_soup.select(".sw-CardBase")
  url_tag_list = []
  for b in base_list:
    if b.get("data-pos"):
      url_tag_list.append(b.a)
  return url_tag_list

# bingで検索する https://www.bing.com/search?q=python&form=QBLH
def search_by_bing(keyword, start):
  url = "https://www.bing.com/search"
  headers = {
      "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"}
  search_params = {"q": keyword, "form": "QBLH", "first": start}
  p_str = "&".join("%s=%s" % (k, v) for k, v in search_params.items())
  search_res = requests.get(url, params=p_str, headers=headers)
  search_soup = BeautifulSoup(search_res.text, 'html.parser')
  # <li class="b_algo"> 直下のaタグが検索結果
  base_list = search_soup.select(".b_algo")
  url_tag_list = []
  for b in base_list:
    url_tag_list.append(b.a)
  return url_tag_list

# URLのタグのリストから指定したドメインのタグを削除する（削除対象のドメインはリストで指定する）
def exclude_specific_domains(url_tag_list, target_list):
  print([u['href'] for u in url_tag_list])
  print(f'{", ".join(target_list)}を除外します')
  escaped_target_list = map(re.escape, target_list)
  target = f'({"|".join(escaped_target_list)})'
  result_list = [url_tag for url_tag in url_tag_list if not re.match(
      f'{target}.*?', url_tag['href'])]
  exclusion_num = len(url_tag_list) - len(result_list)
  if exclusion_num > 0:
    print(f'{exclusion_num}件除外しました')
  else:
    print('除外対象なし') 
  return result_list

# 指定した値までGoogle検索でURLタグをリストアップする(第3引数のドメインを除外した上で)
def get_url_tag_list_up_to_specified_number(keyword, number, exclusion_target_list):
  result_list = []
  loop_index = 0
  while len(result_list) < number:
    url_tag_list = get_url_tag_list(keyword, loop_index * 10)
    url_tag_list_excluding_target_domain = exclusion_target_list and exclude_specific_domains(
        url_tag_list, exclusion_target_list) or url_tag_list
    result_list.extend(url_tag_list_excluding_target_domain)
    loop_index += 1
  return result_list[: number]

# 指定した数までYahoo!で検索する(第3引数のドメインを除外した上で)
def search_by_yahoo_up_to_specified_number(keyword, number, exclusion_target_list):
  result_list = []
  while len(result_list) < number:
    url_tag_list = search_by_yahoo(keyword, len(result_list) + 1)
    url_tag_list_excluding_target_domain = exclusion_target_list and exclude_specific_domains(
        url_tag_list, exclusion_target_list) or url_tag_list
    result_list.extend(url_tag_list_excluding_target_domain)
  return result_list[: number]
  
# 指定した数までbingで検索する(第3引数のドメインを除外した上で)
def search_by_bing_up_to_specified_number(keyword, number, exclusion_target_list):
  result_list = []
  while len(result_list) < number:
    url_tag_list = search_by_bing(keyword, len(result_list) + 1)
    url_tag_list_excluding_target_domain = exclusion_target_list and exclude_specific_domains(
        url_tag_list, exclusion_target_list) or url_tag_list
    result_list.extend(url_tag_list_excluding_target_domain)
  return result_list[: number]

# 通信結果を判定する
def is_res_ng(res):
  try:
    res.raise_for_status()
    # 例外なし => OK出力
    print("通信結果判定：正常")
    return False
  
  except requests.RequestException as e:
    # 例外あり => NG出力
    print("通信結果判定：異常（ページ存在なし等）")
    print(e)
    return True


# ______________________________________________________________________________________________
#
# メイン処理系
# -----------------

# ユーザが指定した番号に応じた検索エンジンで検索を行う
# 外部依存：search_engine
def get_urlList_by_user_selected():
  # 全件URLリスト
  urlList = None
  if search_engine == 1:
    urlList = get_url_tag_list_up_to_specified_number(search_keyword, number_of_pages, exclusion_domain_list)
  elif search_engine == 2:
    urlList = search_by_yahoo_up_to_specified_number(search_keyword, number_of_pages, exclusion_domain_list)
  elif search_engine == 3:
    urlList = search_by_bing_up_to_specified_number(search_keyword, number_of_pages, exclusion_domain_list)
  return urlList

# 例外を考慮した通信処理
def get_res(url: str) -> requests.models.Response:
  
  # 取得したURLにアクセス
  h = {
      "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"}
    
  # 通信実行（例外時はtracebackを出力して関数を終了する）
  try:
    res = requests.get(url, headers=h, verify=False)
  except:
    print("通信時例外発生_例外詳細：")
    # traceback詳細出力
    import traceback
    traceback.print_exc()
    return False
  
  # 通信結果が異常
  if is_res_ng(res):
    return False
  
  # WEBページの文字コードを推測
  res.encoding = res.apparent_encoding
  if res.encoding != 'UTF-8' and res.encoding != 'utf-8':
    print(f'UTF-8以外の文字コードを検出：{res.encoding}')
    if res.encoding == 'Windows-1254':
      print('誤りだと思われる文字コード(Windows-1254)を検出しました。UTF-8に変換します。')
      res.encoding = 'UTF-8'
  
  return res

# 引数のURLのページにアクセス、メインコンテンツらしき文章を抽出する
def extract_content_by_readability(url: str) -> str:
  res = get_res(url)
  html = res.text
  return extract_content_from_html_by_readability(html)

# extractContent3で同上の処理を行う
def extract_content_by_ec3(url: str) -> str:
  res = get_res(url)
  html = res.text
  return extract_content_from_html_by_ec3(html)

# HTMLのテキストからコンテンツ本文を取得する(readabilityを利用)
def extract_content_from_html_by_readability(html: str) -> str:
  article = Document(html).summary()
  text = delete_tag(article)
  return text

# HTMLのテキストからコンテンツ本文を取得する(extract_content_3を利用)
def extract_content_from_html_by_ec3(html: str) -> str:
  # extractContent3
  extractor = ExtractContent()
  # HTML分析
  extractor.analyse(html)
  text, title = extractor.as_text()
  return text

# 本文抽出実行処理
def extract_content_app():

  # 全件URLリスト
  urlList = get_urlList_by_user_selected()

  # URLのリストに基づいてページにアクセスし、本文を抽出する
  for u_tag in urlList:
    url = u_tag['href']

    print("")
    pycolor.print_green(url)
    pycolor.print_green("--------------------\n")
    
    res = get_res(url)
    if not res:
      print("次ページに処理を移行します")
      continue
    
    html = res.text
    text_r = delete_empty(extract_content_from_html_by_readability(html))
    text_ec3 = delete_empty(extract_content_from_html_by_ec3(html))

    pycolor.print_red("library: readability")
    pycolor.print_red(text_r)
    print("")
    pycolor.print_blue("library: extract_content_3")
    pycolor.print_blue(text_ec3)
    print("")


#_________________________________________________
#
#実行処理
#-----------------------------

# タプルで取得：readability使用版とextractcontent3使用版
text_r, text_ec3 = extract_content_app()

wakati_r = write_wakati(text_r)
wakati_ec3 = write_wakati(text_ec3)

model_r = markovify.NewlineText(wakati_r)
model_ec3 = markovify.NewlineText(wakati_ec3)

sentence_r = model_r.make_sentence()
sentence_ec3 = model_ec3.make_sentence()
