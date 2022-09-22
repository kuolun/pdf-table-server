from flask import Flask, render_template, request

# 多執行緒
import threading
import time
from datetime import datetime

# get data
import requests
from bs4 import BeautifulSoup

# 處理路徑問題
from pathlib import Path

app = Flask(__name__)

# constant
DOMAIN = 'https://www.accessdata.fda.gov'


@app.route('/')
def hello_world():  # put application's code here
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    print('search')
    d_name = request.form['device']
    p_code = request.form['product_code']
    print(d_name, p_code)
    helper = SearchHelper(d_name, p_code)
    data_count = helper.search_website()
    return render_template('result.html', d_name=d_name, p_code=p_code, data_count=data_count)


class SearchHelper:
    def __init__(self, d_name: str, p_code: str):
        self.downloaded_pdf = 0
        self.dest_dir = None
        self.url = None
        self.pdf_list = []
        self.d_name = d_name
        self.p_code = p_code

    # 搜尋網站資料筆數
    def search_website(self) -> int:
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

            # 發出多個thread, 等所有thread都跑完才執行後面程式碼
            for x in threads:
                x.join()

            print(f'PDF檔案清單:{self.pdf_list}')

            return data_count

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
            # print(f'pdf下載連結:{pdf_url}')

            # 以目前date+time+keyword當資料夾名稱
            now = datetime.now()
            date_string = now.strftime("%Y%m%d")

            # 取得目前檔案所在路徑
            current_working_dir = Path.cwd()

            # 設定資料夾名稱
            if self.d_name == '':
                self.dest_dir = current_working_dir / 'downloads' / Path(date_string + ' ' + self.p_code)
            elif self.p_code == '':
                self.dest_dir = current_working_dir / 'downloads' / Path(date_string + ' ' + self.d_name)
            else:
                self.dest_dir = current_working_dir / 'downloads' / Path(
                    date_string + ' ' + self.d_name + ' ' + self.p_code)

            # self.dest_dir = 'pdf-download-0822'  # 資料夾名稱

            if not Path.exists(self.dest_dir):  # 建立資料夾
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
        file_path = Path.joinpath(self.dest_dir, file_name )
        print(f'檔案名稱:{file_name}')
        print(f'存放資料夾位置:{file_path}')

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

        # 結束測量
        end = time.time()
        # 輸出結果
        print(f"{file_name}下載時間：", round(end - start, 2))

        self.downloaded_pdf += 1


if __name__ == '__main__':
    app.run()
