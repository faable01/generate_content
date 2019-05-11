import re
import requests
from bs4 import BeautifulSoup
import datetime
from janome.tokenizer import Tokenizer
import random
import markovify
from concurrent.futures import ThreadPoolExecutor
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from readability.readability import Document
from extractcontent3 import ExtractContent
import re
from datetime import datetime

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

# URLリストを保存するためのメモ
memo_url_list = None

# 通信結果を保存するためのメモ
memo_res = {}


# ______________________________________________________________________________________________
#
# global操作系
# -----------------
def write_memo_res(url: str, res: requests.models.Response):
  """
  通信結果をメモに残す
  """
  global memo_res
  memo_res[url] = res

def read_memo_res(url: str) -> requests.models.Response:
  """
  引数で指定したURLの通信結果メモを読む
  """
  return memo_res.get(url)

def write_memo_url_list(urlList: list):
  """
  URLタグのリストをメモに残す
  """
  global memo_url_list
  memo_url_list = urlList

def read_memo_url_list():
  """
  URLタグのリストをメモから取得する
  """
  return memo_url_list


# ______________________________________________________________________________________________
#
# ファイル操作系
# -----------------

def write_next_line(filename, str):
  with open(filename, mode="a", encoding="utf-8") as f:
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
def getSurfaceOf(token_list, part_of_speech) -> list:
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
  if target:
    return target.replace(" ", "")
  else:
    return ""

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
  
  @classmethod
  def print_cyan(self, target: str):
    print(pycolor.paint(target, pycolor.CYAN))


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

    # url_tag_listが一件も存在しない場合にはループを抜ける
    if len(url_tag_list) is 0:
      break
    
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

    # url_tag_listが一件も存在しない場合にはループを抜ける
    if len(url_tag_list) is 0:
      break
    
    url_tag_list_excluding_target_domain = exclusion_target_list and exclude_specific_domains(
        url_tag_list, exclusion_target_list) or url_tag_list
    result_list.extend(url_tag_list_excluding_target_domain)
  return result_list[: number]
  
# 指定した数までbingで検索する(第3引数のドメインを除外した上で)
def search_by_bing_up_to_specified_number(keyword, number, exclusion_target_list):
  result_list = []
  while len(result_list) < number:
    url_tag_list = search_by_bing(keyword, len(result_list) + 1)

    # url_tag_listが一件も存在しない場合にはループを抜ける
    if len(url_tag_list) is 0:
      break
    
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
  
  # メモからの読み取り
  urlList = read_memo_url_list()
  
  # 全件URLリスト
  if not urlList:
    if search_engine == 1:
      urlList = get_url_tag_list_up_to_specified_number(search_keyword, number_of_pages, exclusion_domain_list)
    elif search_engine == 2:
      urlList = search_by_yahoo_up_to_specified_number(search_keyword, number_of_pages, exclusion_domain_list)
    elif search_engine == 3:
      urlList = search_by_bing_up_to_specified_number(search_keyword, number_of_pages, exclusion_domain_list)
  
  # メモへの書き込み
  write_memo_url_list(urlList)

  return urlList

# 例外を考慮した通信処理
def get_res(url: str) -> requests.models.Response:
  
  # 取得したURLにアクセス
  h = {
      "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"}
    
  # 通信結果をメモから取得する（メモにない場合はNone）
  res = read_memo_res(url)

  # メモにない場合は通信実行（例外時はtracebackを出力して関数を終了する）
  if not res:
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

# URLのタグから見出しを取得する
def get_headings(url_tag):
  
  headings = {'h2': [], 'h3': [], 'h4': []}
  
  # 取得したURLにアクセス
  h = {
      "User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.2; ja-jp; SC-06D Build/JZO54K) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"}
  
  # 通信結果をメモから取得する（メモにない場合はNone）
  res = read_memo_res(url_tag['href'])

  # メモにない場合は通信実行（例外時はtracebackを出力して関数を終了する）
  if not res:
    try:
      res = requests.get(url_tag['href'], headers=h, verify=False)
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

  soup = BeautifulSoup(res.text, 'html.parser')

  # 見出し取得
  h_list = soup.select('h2, h3, h4')

  for h in h_list:
    h_text = h.text.strip()

    if h.name == 'h2' and has_kw(must_keyword, h_text):
      headings['h2'].append(h_text and h_text.replace("・", "") or "")

    elif h.name == 'h3' and has_kw(must_keyword, h_text):
      headings['h3'].append(h_text and h_text.replace("・", "") or "")

    elif h.name == 'h4' and has_kw(must_keyword, h_text):
      headings['h4'].append(h_text and h_text.replace("・", "") or "")
  
  return headings

# 引数で指定したURLタグのリストに従い、複数スレッドでアクセス・見出し取得を行う
def multi_get_all_headings(urlList):

  # 全見出し + 名詞,一般　格納変数
  all = {'h2': [], 'h3': [], 'h4': []}

  # 複数スレッドでの関数実行
  with ThreadPoolExecutor() as pool:
    for i, headings in enumerate(pool.map(get_headings, urlList)):
      print(f'{i + 1}件目解析中...')
      
      # 通信失敗時
      if not headings:
        print("次ページに処理を移行します")
        continue
      
      all['h2'].extend([write_wakati(h) for h in headings['h2']])
      all['h3'].extend([write_wakati(h) for h in headings['h3']])
      all['h4'].extend([write_wakati(h) for h in headings['h4']])
      print('完了')

  print('全URLの見出しの取得を完了しました。')
  return all

def markovify_headings(all: dict) -> list:
  # 二次元リストをスペース + 改行区切りで文字列に変換
  all_h2_str = create_str_lines(all['h2'])
  all_h3_str = create_str_lines(all['h3'])
  all_h4_str = create_str_lines(all['h4'])
  all_line = f"{all_h2_str}\n{all_h3_str}\n{all_h4_str}"

  # Build the model.
  text_model = markovify.NewlineText(all_line)

  # ---- 見出し構築・出力 ----

  # 全見出しリスト
  h2_block_list = []

  # h2を3〜5個
  num_h2 = random.randrange(3, 6, 1)
  for i in range(num_h2):

    sentence_h2 = delete_empty(text_model.make_sentence())
    h2_block = {"name": sentence_h2, "content": "", "h3_block_list": []}
    h2_block_list.append(h2_block)

    sentence_h2 and print(sentence_h2)

    # 各h2に対してh3を2~3個
    num_h3 = random.randrange(2, 4, 1)
    for j in range(num_h3):

      sentence_h3 = delete_empty(text_model.make_sentence())
      h3_block = {"name": sentence_h3, "content": "", "h4_block_list": []}
      h2_block["h3_block_list"].append(h3_block)

      sentence_h3 and print(f'・{sentence_h3}')
      
      # h3に対して3回に1回の割合くらいでh4を2~3個
      num_h4 = random.choice([0, 0, 0, 0, 2, 3])
      for k in range(num_h4):
        
        sentence_h4 = delete_empty(text_model.make_sentence())
        h4_block = {"name": sentence_h4, "content": ""}
        h3_block["h4_block_list"].append(h4_block)

        sentence_h4 and print(f'・・{sentence_h4}')
    
    print('')
    return h2_block_list

# マルコフ連鎖で見出しを自動生成する
def markovify_headings_app() -> list:

  # 全件URLリスト
  urlList = get_urlList_by_user_selected()

  # URLリストの要素が存在しない場合、処理を終了する
  if len(urlList) is 0:
    return
  
  # 全見出し　{'h2': [...], 'h3': [...], 'h4': [...]}
  all = multi_get_all_headings(urlList)

  loop_count = 1
  while True:
    print('\n____________________________________________\n')
    print(f'構成案 {loop_count}件目\n---------------------------\n')

    # マルコフ連鎖で見出しを自動生成する
    all_block_list = markovify_headings(all)

    is_retry = ""
    while is_retry != 'YES' and is_retry != 'NO':
      is_retry = input('この見出しで本文を作成しますか？ ( YES / NO ) >>> ')

      if is_retry == 'YES' or is_retry == 'yes' or is_retry == 'y' or is_retry == 'Y':
        is_retry = 'YES'
      elif is_retry == 'NO' or is_retry == 'no' or is_retry == 'n' or is_retry == 'N':
        is_retry = 'NO'

    if is_retry == 'YES':
      break
    elif is_retry == 'NO':
      loop_count += 1
    
  return all_block_list

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

# optionを指定してコンテンツ本文を取得する（extractcontent3を利用）
def extract_content_from_html_by_ec3_according_to_option(html: str, option: dict) -> str:
  # extractContent3
  extractor = ExtractContent()
  # オプション値を指定する
  extractor.set_option(option)
  # HTML分析
  extractor.analyse(html)
  text, title = extractor.as_text()
  return text

# extractcontent3用のオプションを作成する
def create_option_for_ec3(threshold=100, min_length=80, decay_factor=0.73, continuous_factor=1.62, punctuation_weight=10) -> dict:
  """
  オプションの種類:
  名称 / デフォルト値
  
  threshold / 100
  本文と見なすスコアの閾値
  
  min_length / 80
  評価を行うブロック長の最小値
  
  decay_factor / 0.73
  減衰係数
  小さいほど先頭に近いブロックのスコアが高くなります
  
  continuous_factor / 1.62
  連続ブロック係数
  大きいほどブロックを連続と判定しにくくなる
  
  punctuation_weight / 10
  句読点に対するスコア
  大きいほど句読点が存在するブロックを本文と判定しやすくなる
  """
  option = {
    "threshold": threshold,
    "min_length": min_length,
    "decay_factor": decay_factor,
    "continuous_factor": continuous_factor,
    "punctuation_weight": punctuation_weight
  }
  return option

# 本文抽出
def extract_content_app() -> list:

  # 全件URLリスト
  urlList = get_urlList_by_user_selected()

  # URLリストの要素が存在しない場合、処理を終了する
  if len(urlList) is 0:
    return
  
  # 全件本文
  contents_list = []

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
    option = create_option_for_ec3(10, 80, 1.00, 1.00, 10) # 有力候補
    text_ec3 = delete_empty(extract_content_from_html_by_ec3_according_to_option(html, option))

    pycolor.print_blue("### Result for extracting content")
    pycolor.print_blue(text_ec3)
    print("")
    
    contents_list.append(text_ec3)
  
  return contents_list

# 複数スレッドで本文抽出を行う
def multi_extract_content_app() -> list:

  # 全件URLリスト
  urlList = get_urlList_by_user_selected()

  # URLリストの要素が存在しない場合、処理を終了する
  if len(urlList) is 0:
    return
  
  # 全件本文
  contents_list = []

  # 複数スレッドでの関数実行
  with ThreadPoolExecutor() as pool:
    urls = [u['href'] for u in urlList]
    for i, res in enumerate(pool.map(get_res, urls)):
      print("")
      pycolor.print_green(urls[i])
      pycolor.print_green("--------------------\n")
      
      if not res:
        print("次ページに処理を移行します")
        continue
      
      html = res.text
      # option = create_option_for_ec3(10, 80, 1.00, 1.00, 10) # 検索件数が少ない場合はこっち(精度は低いが多く情報取得できる)
      option = create_option_for_ec3()
      text_ec3 = delete_empty(extract_content_from_html_by_ec3_according_to_option(html, option))
  
      pycolor.print_blue("### Result for extracting content")
      pycolor.print_blue(text_ec3)
      print("")
      
      contents_list.append(text_ec3)
  
  return contents_list


# 文章自動生成
def generate_content(text, *, first_word="", first_word_list=[]):
  wakati = write_wakati(text)
  model = markovify.NewlineText(wakati)
  all_sentence = ""
  next_start_word = first_word

  if len(first_word_list):
    for w in first_word_list:
      try:
        model.make_sentence_with_start(w)
      except:
        continue
      next_start_word = w
      break

  for i in range(10):

    sentence = ""
    # print(f"next: {next_start_word}")
    if next_start_word:
      try:
        sentence = delete_empty(model.make_sentence_with_start(next_start_word))
      except:
        next_start_word = ""
        sentence = ""
      
    else:
      sentence = delete_empty(model.make_sentence())

    all_sentence += f"\n{sentence}"

    token_list = t.tokenize(sentence)
    noun_list = getSurfaceOf(token_list, '名詞,一般')
    noun_list_len = len(noun_list)
    
    for i in range(noun_list_len):
      # print(f"{i} / {noun_list_len - 1}")
      target_index = noun_list_len - 1 - i
      target_noun = noun_list[target_index]
      
      if next_start_word == target_noun:
        if i is noun_list_len - 1:
          # print("same as before")
          # print("go to next loop")
          next_start_word = ""
          break
        
        else:
          continue

      try:
        model.make_sentence_with_start(target_noun)
      except:
        if i is noun_list_len - 1:
          # print("model nothing")
          # print("go to next loop")
          next_start_word = ""
          break
        
        else:
          continue
      
      # print(f"swap: {next_start_word}, {target_noun}")
      next_start_word = target_noun
      break

  return all_sentence

# 本文自動生成
def generate_content_app():
  
  # 全本文
  contents_list = multi_extract_content_app()
  all_contents_text = "\n".join(contents_list)
  
  loop_count = 1
  while True:

    # マルコフ連鎖で本文を自動生成する
    result = generate_content(all_contents_text)

    pycolor.print_cyan('\n____________________________________________\n')
    pycolor.print_cyan(f'構成案 {loop_count}件目\n---------------------------\n')
    pycolor.print_cyan(result)
    print("")

    is_retry = ""
    while is_retry != 'YES' and is_retry != 'NO':
      is_retry = input('もう一度見出しのシャッフル・再構築を実行しますか？ ( YES / NO ) >>> ')

      if is_retry == 'YES' or is_retry == 'yes' or is_retry == 'y' or is_retry == 'Y':
        is_retry = 'YES'
      elif is_retry == 'NO' or is_retry == 'no' or is_retry == 'n' or is_retry == 'N':
        is_retry = 'NO'

    if is_retry == 'YES':
      loop_count += 1
    elif is_retry == 'NO':
      break

def generate_page_app() -> list:
  """
  ページの自動生成を行う実行メソッド
  """

  """
  h2_block_list: [
    {
      "name": h2の見出し,
      "content": h2の本文（この時点では空文字）,
      "h3_block_list": [
        {
          "name": h3の見出し,
          "content": h3の本文（この時点では空文字）,
          "h4_block_list": [
            {
              "name": h4の見出し,
              "content": h4の本文
            }
          ]
        }
      ]
    }
  ]
  """
  h2_block_list = markovify_headings_app()

  # URLが存在せず、見出しの自動生成に失敗した場合は処理を終了する
  if h2_block_list is None:
    print("元となる情報を取得するためのURLが存在しませんでした。自動生成処理を終了します。")
    return
  
  # 全本文
  contents_list = multi_extract_content_app()
  all_contents_text = "\n".join(contents_list)

  # 作成した見出しの再出力
  pycolor.print_cyan('\n____________________________________________\n')
  pycolor.print_cyan(f'見出し構成\n---------------------------\n')
    
  # h2
  for i, h2_block in enumerate(h2_block_list):
    h2_name = h2_block["name"]
    pycolor.print_cyan(f"{h2_name}")
    h3_block_list = h2_block_list[i]["h3_block_list"]

    # h3
    for i, h3_block in enumerate(h3_block_list):
      h3_name = h3_block["name"]
      pycolor.print_cyan(f"・{h3_name}")
      h4_block_list = h3_block_list[i]["h4_block_list"]

      # h4
      for i, h4_block in enumerate(h4_block_list):
        h4_name = h4_block["name"]
        pycolor.print_cyan(f"・・{h4_name}")

  print("")

  # 本文の自動生成
  loop_count = 1
  while True:

    # 複数スレッド実行用
    noun_list_list = []
    
    # 見出しの名詞リストを取得
    # h2
    for i, h2_block in enumerate(h2_block_list):
      h2_name = h2_block["name"]
      noun_list = list(reversed(getSurfaceOf(t.tokenize(h2_name), "名詞,一般")))
      noun_list_list.append(noun_list)

      h3_block_list = h2_block_list[i]["h3_block_list"]
  
      # h3
      for i, h3_block in enumerate(h3_block_list):
        h3_name = h3_block["name"]
        noun_list = getSurfaceOf(t.tokenize(h3_name), "名詞,一般")
        noun_list_list.append(noun_list)

        h4_block_list = h3_block_list[i]["h4_block_list"]
  
        # h4
        for i, h4_block in enumerate(h4_block_list):
          h4_name = h4_block["name"]
          noun_list = getSurfaceOf(t.tokenize(h4_name), "名詞,一般")
          noun_list_list.append(noun_list)

    # 複数スレッド結果格納用
    content_list = []

    # # 見出しの名詞リストから本文の自動生成を複数スレッドで行う
    # with ThreadPoolExecutor() as pool:
    #   for i, content in enumerate(pool.map(lambda nouns: len(nouns) and generate_content(all_contents_text, first_word_list=nouns) or generate_content(all_contents_text), noun_list_list)):
    #     print(f'{i + 1}ブロック目自動生成完了...')
    #     content_list.append(content)

    # 見出しの名詞リストから本文の自動生成を単独スレッドで行う
    for i, noun_list in enumerate(noun_list_list):
      print(f'{i + 1}ブロック目自動生成中...')
      content = len(noun_list) and generate_content(all_contents_text, first_word_list=noun_list) or generate_content(all_contents_text)
      content_list.append(content)
      print("完了")


    pycolor.print_cyan('\n____________________________________________\n')
    pycolor.print_cyan(f'本文構成案 {loop_count}件目\n---------------------------\n')
    
    # 自動生成した本文を出力する
    # h2
    content_list_index = 0
    for i, h2_block in enumerate(h2_block_list):
      h2_content = content_list[content_list_index]
      content_list_index += 1
      h2_block_list[i]["content"] = h2_content

      pycolor.print_cyan(f"## {h2_name}")
      pycolor.print_cyan(f"見出し2_本文：\n{h2_content}\n")

      h3_block_list = h2_block_list[i]["h3_block_list"]
  
      # h3
      for i, h3_block in enumerate(h3_block_list):
        h3_content = content_list[content_list_index]
        content_list_index += 1
        h3_block_list[i]["content"] = h3_content

        pycolor.print_cyan(f"### {h3_name}")
        pycolor.print_cyan(f"見出し3_本文：\n{h3_content}\n")

        h4_block_list = h3_block_list[i]["h4_block_list"]
  
        # h4
        for i, h4_block in enumerate(h4_block_list):
          h4_content = content_list[content_list_index]
          content_list_index += 1
          h4_block_list[i]["content"] = h4_content
          
          pycolor.print_cyan(f"#### {h4_name}")
          pycolor.print_cyan(f"見出し4_本文：\n{h4_content}\n")
    
    print("")

    # ファイル書き込み判定
    does_write_file = ""
    while does_write_file != 'YES' and does_write_file != 'NO':
      does_write_file = input('生成した見出しと本文をHTMLファイルとしてエクスポートしますか？ ( YES / NO ) >>> ')

      if does_write_file == 'YES' or does_write_file == 'yes' or does_write_file == 'y' or does_write_file == 'Y':
        does_write_file = 'YES'
      elif does_write_file == 'NO' or does_write_file == 'no' or does_write_file == 'n' or does_write_file == 'N':
        does_write_file = 'NO'
    
    # ファイル書き込み実行
    if does_write_file == 'YES':

      filename = f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}_{search_keyword}.html"

      write_next_line(filename, "<!doctype html>")
      write_next_line(filename, '<html><head><meta charset="UTF-8"></head><body>')
  
      # マルコフ連鎖でページを自動生成する
      # h2
      for i, h2_block in enumerate(h2_block_list):
        h2_name = h2_block["name"]
        h2_content = h2_block["content"]
      
        write_next_line(filename, f"<h2>{h2_name}</h2>")
        h2_content_for_html = h2_content.replace('\n', '<br/>')
        write_next_line(filename, f"<div>{h2_content_for_html}</div>")
    
        h3_block_list = h2_block_list[i]["h3_block_list"]
    
        # h3
        for i, h3_block in enumerate(h3_block_list):
          h3_name = h3_block["name"]
          h3_content = h3_block["content"]
          
          write_next_line(filename, f"<h3>{h3_name}</h3>")
          h3_content_for_html = h3_content.replace('\n', '<br/>')
          write_next_line(filename, f"<div>{h3_content_for_html}</div>")
  
          h4_block_list = h3_block_list[i]["h4_block_list"]
    
          # h4
          for i, h4_block in enumerate(h4_block_list):
            h4_name = h4_block["name"]
            h4_content = h4_block["content"]
  
            write_next_line(filename, f"<h4>{h4_name}</h4>")
            h4_content_for_html = h4_content.replace('\n', '<br/>')
            write_next_line(filename, f"<div>{h4_content_for_html}</div>")
              
      write_next_line(filename, "</body></html>")
    
    # 本文再生成判定
    is_retry = ""
    while is_retry != 'YES' and is_retry != 'NO':
      is_retry = input('もう一度本文の自動生成を行いますか？ ( YES / NO ) >>> ')

      if is_retry == 'YES' or is_retry == 'yes' or is_retry == 'y' or is_retry == 'Y':
        is_retry = 'YES'
      elif is_retry == 'NO' or is_retry == 'no' or is_retry == 'n' or is_retry == 'N':
        is_retry = 'NO'

    if is_retry == 'YES':
      loop_count += 1
    elif is_retry == 'NO':
      break
  
  return h2_block_list


#_________________________________________________
#
#実行処理
#-----------------------------
def initialize():
  """
  再実行用にglobal変数を再設定する
  """
  # ユーザ入力 >>> シャッフル元ページの取得件数
  global number_of_pages
  number_of_pages = int(input('シャッフル元となるページの取得件数を入力してください >>> '))
  
  # ユーザ入力 >>> 除外するドメインのリスト
  global user_input
  global exclusion_domain_list
  user_input = input('除外するドメインを指定してください（スペースを空けて複数指定可能） >>> ').strip() or None
  exclusion_domain_list = user_input and user_input.split() or []
  
  # 検索エンジンの指定
  global search_engine
  search_engine = 0
  while not search_engine in (1, 2, 3):
    search_engine = int(input('検索エンジンを選択してください。 1. Google, 2. Yahoo!, 3. Bing（1, 2, 3のどれかを押してください） >>> '))
  
  # ユーザ入力 >>> 検索キーワード
  global search_keyword
  search_keyword = '+'.join(input('検索キーワードを入力してください >>> ').split())
  
  # デフォルトの削除ドメイン
  default_exclusion_domain_list = ["https://www.amazon.co.jp/", "https://www.rakuten.co.jp/", "https://kakaku.com/", "https://twitter.com/", "https://www.instagram.com/", "https://www.cosme.net/", "https://beauty.hotpepper.jp/", "https://search.rakuten.co.jp/"]
  exclusion_domain_list.extend(default_exclusion_domain_list)
  
  # 必須KW
  global must_keyword
  must_keyword = input('必須キーワードを入力してください >>> ')
  
  # URLリストを保存するためのメモ
  global memo_url_list
  memo_url_list = None
  
def app():
  """
  実行メソッド
  """
  while True:
    generate_page_app()
    
    is_retry = ""
    while is_retry != 'YES' and is_retry != 'NO':
      is_retry = input('新たにキーワード等を指定して、見出し・本文の自動生成を行いますか？ ( YES / NO ) >>> ')
      if is_retry == 'YES' or is_retry == 'yes' or is_retry == 'y' or is_retry == 'Y':
        is_retry = 'YES'
      elif is_retry == 'NO' or is_retry == 'no' or is_retry == 'n' or is_retry == 'N':
        is_retry = 'NO'
    
    if is_retry == 'YES':
      initialize()
      continue
    elif is_retry == 'NO':
      break

# 処理実行
app()