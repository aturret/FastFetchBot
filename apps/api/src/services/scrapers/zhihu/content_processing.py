from urllib.parse import urlparse, parse_qs, unquote

from bs4 import BeautifulSoup


def fix_images_and_links(html: str) -> str:
    """
    Port of FxZhihu's fixImagesAndLinks:
    - Replace data-actualsrc with src on img tags
    - Remove <u> tags preserving text content
    """
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img"):
        actualsrc = img.get("data-actualsrc")
        if actualsrc:
            img["src"] = actualsrc
            del img["data-actualsrc"]
    for u_tag in soup.find_all("u"):
        u_tag.unwrap()
    return str(soup)


def extract_references(html: str) -> str:
    """
    Port of FxZhihu's extractReference:
    - Find <sup> tags with data-text, data-url, data-numero
    - Return formatted reference list HTML
    """
    soup = BeautifulSoup(html, "html.parser")
    references = {}
    for sup in soup.find_all("sup"):
        text = sup.get("data-text")
        url = sup.get("data-url", "")
        numero = sup.get("data-numero")
        if text and numero:
            references[numero] = {"text": text, "url": url}
    if not references:
        return ""
    sorted_refs = sorted(references.items(), key=lambda x: int(x[0]))
    items = []
    for index, ref in sorted_refs:
        url_html = f'<a href="{ref["url"]}">{ref["url"]}</a>' if ref["url"] else ""
        items.append(f"<li>{ref['text']}{url_html}</li>")
    return f'<hr><section><h2>参考</h2><ol>{"".join(items)}</ol></section>'


def unmask_zhihu_links(html: str) -> str:
    """
    Port of FxZhihu's link unmasking:
    - Decode https://link.zhihu.com/?target=... to actual URLs
    """
    soup = BeautifulSoup(html, "html.parser")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("https://link.zhihu.com/"):
            try:
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                target = qs.get("target", [None])[0]
                if target:
                    a_tag["href"] = unquote(target)
            except Exception:
                pass
    return str(soup)
