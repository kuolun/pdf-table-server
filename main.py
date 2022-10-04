# third-party library
from flask import Flask, render_template, request

# get data
import requests
from bs4 import BeautifulSoup

# 偵測Comparison文字在第幾頁
# import PyPDF2
from PyPDF2 import PdfReader

# table轉df
import camelot
# import pandas as pd
from pandas import concat

import glob
import os
# 多執行緒
import threading
import time

# 處理壓縮檔
import zipfile
from datetime import datetime

# 處理路徑問題
from pathlib import Path
from typing import Tuple, List, Any

# import re
from re import search

# 刪除資料夾
import shutil

app = Flask(__name__)

# constant
DOMAIN = 'https://www.accessdata.fda.gov'


@app.route('/')
def hello_world():  # put application's code here
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search_site():
    print('search')
    d_name = request.form['device']
    p_code = request.form['product_code']
    print(d_name, p_code)
    helper = SearchHelper(d_name, p_code)
    data_count, pdf_list, zip_file = helper.search_website()
    return render_template(
        'result.html',
        d_name=d_name,
        p_code=p_code,
        data_count=data_count,
        pdf_list=pdf_list,
        zip_file=zip_file
    )


class SearchHelper:
    def __init__(self, d_name: str, p_code: str):
        # zip檔
        self.zip_file = None
        # 已下載pdf數量
        self.downloaded_pdf = 0
        # 存檔路徑
        self.dest_dir = None
        self.url = None
        self.pdf_list = []
        self.d_name = d_name
        self.p_code = p_code
        self.pdf_download_file = []  # 下載pdf存放url清單

    def find_text(self, search_file, search_string):
        # xfile :  PDF file to search
        # x_string :  string to search
        page_found = 0

        if not Path.exists(search_file):
            # 無此檔案
            return 0, 0
        else:
            reader = PdfReader(search_file)
            number_of_pages = len(reader.pages)
            print(f"{search_file}--總頁數:{number_of_pages}\n")

            for page in reader.pages:
                text = page.extract_text().lower()
                res_search = search(search_string, text)
                page_number = reader.get_page_number(page)
                print(f'page:{page_number + 1}搜尋結果:{res_search}\n')
                # 找到第一次出現的頁數就跳出
                if res_search is not None:
                    page_found = page_number + 1
                    break

            return page_found, number_of_pages

    def export_html(self):
        threads = []
        print('轉換HTML中...')
        for key in self.pdf_list:
            file = key
            file_path = Path(self.dest_dir) / f'{file}.pdf'
            print(f'檔案:{file}\n')
            print(f'檔案路徑:{file_path}\n')
            # 用多執行緒去跑self.pdf_to_table
            thread_obj = threading.Thread(
                target=self.pdf_to_table,
                args=[file, file_path])  # 建立執行緒物件+傳入參數
            # 加入到thread list
            threads.append(thread_obj)

        # 開始所有thread
        for t in threads:
            t.start()

        # 發出多個thread, 等所有thread都跑完才執行後面程式碼
        for x in threads:
            x.join()

        print("HTML轉檔完成")

    def pdf_to_table(self, file, file_path):
        # 追蹤thread
        current_thread = threading.current_thread()

        print(f'目前thread id:{current_thread.ident}')
        print(f"轉換{file}為HTML中...\n")
        print(f'檔案路徑:{file_path}')

        # 開始測量
        start = time.time()
        table_page_found, total_pages = self.find_text(file_path, 'comparison')
        # 結束測量
        end = time.time()
        print(f'找{file}的comparison文字執行時間:{round(end - start, 2)}\n')
        print(f'table_page_found頁數:{table_page_found}\n')

        # 如果有找到compariosn文字
        if table_page_found:
            print(f'{file}的comparison table開始頁數:{table_page_found}')

            # 開始測量
            start = time.time()

            # 沒pages參數預設只抓第一頁
            # camelot.read_pdf需要的檔案路徑要為string，要把pathlib的obj轉成string
            # filepath (str) – Filepath or URL of the PDF file.
            file_path_str = str(file_path)
            tables = camelot.read_pdf(file_path_str, pages=f"{table_page_found}-end", strip_text='\n')

            # 結束測量
            end = time.time()
            print(f'{file}找table執行時間:{round(end - start, 2)}\n')

            print(f'{file}table數:{len(tables)}')

            for i in range(0, len(tables)):
                table_report = tables[i].parsing_report
                accuracy = round(table_report['accuracy'])
                print(f"tables[{i}]表格準確度為:{accuracy}")
                # table在第幾頁
                table_at_page = tables[i].page
                output_path = self.dest_dir / f"{file}-page{table_at_page}-table{i}-acc{accuracy}.html"
                tables[i].to_html(output_path)
            print(f"=====匯出{file}的table HTML檔完成！=====")
        else:
            print(f"{file}沒有comparison的table\n")

    # 搜尋網站資料筆數
    def search_website(self) -> Tuple[int, List[Any], str]:

        # 先清空static/downloads內所有檔案
        downloads_folder_path = Path.cwd() / 'static/downloads'
        shutil.rmtree(downloads_folder_path)
        os.mkdir(downloads_folder_path)

        self.url = f'{DOMAIN}/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?' \
                   f'start_search=1&Panel=' \
                   f'&DeviceName={self.d_name}' \
                   f'&ProductCode={self.p_code}&PAGENUM=500'

        # 發送search request
        try:
            page = requests.get(self.url, timeout=10)
            if page.status_code == 503:
                page.raise_for_status()
        except requests.ReadTimeout:
            print('連線超過10秒...')
        except requests.exceptions.HTTPError:
            print(" Connection Error...")
        else:
            soup = BeautifulSoup(page.text, features='lxml')

            # 抓取所有要進入detail的連結如:k221259
            # result = soup.find_all(align='Middle')
            search_result = soup.find_all(align='Middle')

            print(f'result type:{type(search_result)}')
            print(f'result:{search_result}')

            data_count = len(search_result)

            print(data_count)

            threads = []

            # 從搜尋到的多個連結，進入detail的連結中找到pdf url
            for item in search_result:
                link = item.find('a')

                id_key = link.getText()

                self.pdf_list.append(id_key)

                detail_page_url = DOMAIN + link.attrs['href']

                print(detail_page_url)

                # 用多執行緒去跑
                # 建立執行緒物件+傳入參數
                thread_obj = threading.Thread(
                    target=self.send_detail_page_request,
                    args=[detail_page_url, id_key]
                )
                threads.append(thread_obj)

                # 開始每個子執行緒
            for t in threads:
                t.start()
                print('thread starting..')
                # 緩衝發送requests
                time.sleep(0.5)

            # 發出多個thread, 等所有thread都跑完才執行後面程式碼
            for x in threads:
                x.join()

            print(f'PDF檔案清單:{self.pdf_list}')
            print(f'PDF檔案URL清單:{self.pdf_download_file}')

            # 把PDF_list轉成HTML
            self.export_html()

            # 處理壓縮
            # 如果要將整個目錄壓縮, 需要將整個目錄讀取一次, 包括裡面的副目錄, 然後逐個檔案加入 zip 檔
            # os.walk()回傳3個值:dirName,sub_dirNames,fileNames

            zip_name = Path(self.dest_dir).parts[-1]  # 抓資料夾名稱當壓縮檔名稱
            zip_file_name = f'{zip_name}.zip'

            # zip檔位置預設會跟main.py在同一層
            # ZipFile第一個參數:path to ZIP file(string)
            # path必須要存在才不會有error
            file_zip = zipfile.ZipFile(f'static/downloads/{zip_file_name}', 'w')
            print(f'要壓縮的目錄:{self.dest_dir}')
            for name in glob.glob(f'{self.dest_dir}/*'):
                print(name)
                file_zip.write(name, os.path.basename(name), zipfile.ZIP_DEFLATED)

            file_zip.close()

            self.zip_file = f'static/downloads/{zip_file_name}'

            return data_count, self.pdf_list, self.zip_file

    def send_detail_page_request(self, detail_page_url, id_key):
        # 發送detail頁面 request
        detail_page_content = requests.get(detail_page_url)

        soup = BeautifulSoup(detail_page_content.text, features='lxml')

        # 若找不到result會拿到None
        result = soup.find(title=f'PDF for {id_key}')

        print(f'尋找PDF檔案URL結果:{result}')

        # 如果有找到pdf檔連結
        if result:
            pdf_url = result['href']
            # print(f' pdf下載連結:{pdf_url}')

            # 以目前date+time+keyword當資料夾名稱
            now = datetime.now()
            date_string = now.strftime("%Y%m%d")

            # 取得目前檔案所在路徑
            current_working_dir = Path.cwd()

            # 設定資料夾名稱
            if self.d_name == '':
                self.dest_dir = current_working_dir / 'static/downloads' / Path(date_string + ' ' + self.p_code)
            elif self.p_code == '':
                self.dest_dir = current_working_dir / 'static/downloads' / Path(date_string + ' ' + self.d_name)
            else:
                self.dest_dir = current_working_dir / 'static/downloads' / Path(
                    date_string + ' ' + self.d_name + ' ' + self.p_code)

            # 若資料夾不存在則建立新的
            if not Path.exists(self.dest_dir):
                self.dest_dir.mkdir(parents=True)

            # 發送下載pdf request
            self.download_pdf(pdf_url)
        else:
            print(f'{detail_page_url}沒有PDF檔')

    def download_pdf(self, url):
        print(f'下載PDF網址:{url}')

        # 設定存檔路徑及存檔名稱
        # https://www.accessdata.fda.gov/cdrh_docs/pdf22/K221259.pdf
        # file_name = path.join(self.dest_dir, path.basename(url))
        # 組出存檔路徑
        file_name = Path(url).name
        file_path = Path.joinpath(self.dest_dir, file_name)
        print(f'檔案名稱:{file_name}')
        print(f'存放檔案位置:{file_path}')

        # 開始測量
        start = time.time()

        pdf = requests.get(url)

        # 寫入檔案
        f = open(file_path, 'wb')
        print(f'{file_path}下載中...')

        for chunk in pdf.iter_content(chunk_size=255):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)

        print(f"{file_name}下載完畢!!")

        f.close()

        self.pdf_download_file.append(file_name)

        # 結束測量
        end = time.time()
        # 輸出結果
        print(f"{file_name}下載時間：", round(end - start, 2))

        self.downloaded_pdf += 1


if __name__ == '__main__':
    app.run()
