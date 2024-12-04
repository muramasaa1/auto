import os
from ftplib import FTP
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta
import time
import pandas as pd
import glob
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

download_folder = "./downloads"
os.makedirs(download_folder, exist_ok=True)

# Настройки Chrome
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_experimental_option("prefs", {"download.default_directory": os.path.abspath(download_folder)})

# Инициализация драйвера
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# Переход на сайт
driver.get("https://bi.datawiz.io")
wait = WebDriverWait(driver, 30)

# Вводим логин и пароль
email_field = wait.until(EC.visibility_of_element_located((By.NAME, "auth-username")))
email_field.send_keys("zhunussova.b@applecity.kz")

password_field = wait.until(EC.visibility_of_element_located((By.NAME, "auth-password")))
password_field.send_keys("Balki852*%@")

# Логинимся
login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
login_button.click()

# Открытие дашборда
dashboards_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/c/154/dashboards']")))
dashboards_link.click()

try:
    available_dashboard_link = wait.until(EC.presence_of_element_located((By.XPATH, "//a[@href='/c/154/dashboard-group/shared-to-me']")))
    driver.execute_script("arguments[0].scrollIntoView(true);", available_dashboard_link)
    driver.execute_script("arguments[0].click();", available_dashboard_link)
except ElementClickInterceptedException:
    print("Не удалось кликнуть на элемент, он перекрыт другим.")
except TimeoutException:
    print("Элемент не найден или не был доступен в течение времени ожидания.")
except Exception as e:
    print(f"Произошла ошибка: {e}")

# Открытие отчёта
open_button = wait.until(EC.presence_of_element_located((By.XPATH, "//div[text()='P&G (Stock)']/following::button[span[text()='Открыть']]")))
driver.execute_script("arguments[0].scrollIntoView(true);", open_button)
open_button.click()

# Настройка фильтров
filters_button = wait.until(EC.presence_of_element_located((By.XPATH, "//span[@class='side-button__text' and text()='Фильтры']")))
driver.execute_script("arguments[0].scrollIntoView(true);", filters_button)
driver.execute_script("arguments[0].click();", filters_button)

# Задаём дату
yesterday = (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y")

start_date_field = wait.until(EC.visibility_of_element_located((By.ID, "date_range")))
start_date_field.click()
start_date_field.send_keys(yesterday)

end_date_field = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='Конечная дата']")))
driver.execute_script("arguments[0].click();", end_date_field)
end_date_field.send_keys(yesterday)
end_date_field.send_keys(Keys.ENTER)

# Применение фильтров
apply_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Применить']")))
apply_button.click()

try:
    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "ant-picker-panel-container")))
except TimeoutException:
    print("Элемент не исчез в течение заданного времени, продолжаем выполнение.")

# Сохранение файла
time.sleep(2)
more_button = wait.until(EC.presence_of_element_located((By.XPATH, "//button[@title='Больше']")))
more_button.click()

save_xls_button = wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='Сохранить XLS']")))
save_xls_button.click()

# Ожидание загрузки файла
def wait_for_file(download_folder, file_pattern, timeout=300):
    start_time = time.time()
    while time.time() - start_time < timeout:
        files = glob.glob(os.path.join(download_folder, file_pattern))
        if files:
            print(f"Найден файл: {files[0]}")
            return files[0]
        print("Файл не найден. Ждем ещё...")
        time.sleep(10)
    raise TimeoutException("Файл не загрузился в течение времени ожидания")

try:
    downloaded_file = wait_for_file(download_folder, f"*30 дней ({yesterday}_{yesterday})*.xlsx", timeout=300)
    print(f"Файл успешно загружен: {downloaded_file}")
except TimeoutException:
    print("Файл не загрузился в течение времени ожидания. Проверьте настройки.")
    driver.quit()
    exit(1)

# Обработка файла
try:
    df = pd.read_excel(downloaded_file)
    print("Колонки в загруженном файле:", df.columns.tolist())

    if df.empty:
        raise ValueError("Файл пустой. Проверьте загруженные данные.")

    df = df.rename(columns={
        "Идентификатор": "BarCode",
        "Название магазина": "StoreCode",
        "Кол-во продаж": "Sell-out",
        "Кол-во остатков на конец дня": "Remains"
    })

    print("Переименованные колонки:", df.columns.tolist())

    df["StoreCode"] = (
        df["StoreCode"]
        .str.replace("С/о", "", regex=False)
        .str.replace("Производство", "", regex=False)
        .str.strip()
    )

    df = df[:-1]
    df["BarCode"] = pd.to_numeric(df["BarCode"], errors='coerce')

    file_date = datetime.strptime(yesterday, "%d-%m-%Y").strftime("%Y%m%d")
    df["Date"] = int(file_date)

    if "VendorCode" not in df.columns:
        df["VendorCode"] = None
    df["Price"] = 0

    df["Sell-out"] = df["Sell-out"].apply(lambda x: x if x >= 0 else 0)
    df["Remains"] = df["Remains"].apply(lambda x: x if x >= 0 else 0)

    df = df[~((df["Price"] == 0) & (df["Sell-out"] == 0) & (df["Remains"] == 0))]

    df = df[["Date", "BarCode", "VendorCode", "StoreCode", "Price", "Sell-out", "Remains"]]

    ftp = FTP('cloud.applecity.kz')
    try:
        ftp.login('CDL_SKIF_CC', 'MKDLKj09jij202!')
        ftp.set_pasv(True)
        ftp.cwd('SKIF_CC/InBox')

        current_time = datetime.now().strftime("%Y%m%d%H%M")
        remote_file_name = f"{current_time}69_SalesRemains_PY_day.xlsx"

        local_path = os.path.join(download_folder, remote_file_name)
        df.to_excel(local_path, index=False, sheet_name="Sheet1")

        with open(local_path, 'rb') as local_file:
            ftp.storbinary(f'STOR {remote_file_name}', local_file)

        print(f"Файл успешно загружен на FTP: {remote_file_name}")

    except Exception as e:
        print(f"Ошибка FTP: {e}")
    finally:
        ftp.quit()

except Exception as e:
    print(f"Ошибка обработки файла: {e}")

driver.quit()
print("Готово")
