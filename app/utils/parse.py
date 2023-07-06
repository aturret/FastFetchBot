import datetime

from bs4 import BeautifulSoup


def get_html_text_length(html: str) -> int:
    if html is None:
        return 0
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    return len(text)


def format_telegram_short_text(soup: BeautifulSoup) -> BeautifulSoup:
    decompose_list = ["br"]
    unwrap_list = ["span", "div", "blockquote", "h2"]
    for decompose in decompose_list:
        for item in soup.find_all(decompose):
            item.decompose()
    for unwrap in unwrap_list:
        for item in soup.find_all(unwrap):
            item.unwrap()
    return soup


def unix_timestamp_to_utc(timestamp):
    utc_time = datetime.datetime.utcfromtimestamp(timestamp)
    beijing_time = utc_time + datetime.timedelta(hours=8)
    return beijing_time.strftime("%Y-%m-%d %H:%M")


def second_to_time(second):
    m, s = divmod(second, 60)
    h, m = divmod(m, 60)
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)
