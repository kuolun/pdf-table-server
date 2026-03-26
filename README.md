# PDF Table Server

Flask 網頁應用，從 FDA 網站擷取 PDF 檔案中的表格資料，支援批次處理與匯出。

## 技術

- Python / Flask
- Camelot（PDF 表格擷取）
- PyPDF2 / BeautifulSoup
- Requests（FDA 資料抓取）
- Gunicorn 部署
