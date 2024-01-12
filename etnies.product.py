import re
import ast
import json
import requests
import traceback
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

import openpyxl
from selenium import webdriver

from helper import (
    extract_style_code,
    singularize,
    switch_words,
    getPrice,
    remove_double_spaces,
)
from script import (
    get_walmart_product_data,
    get_shopify_product_data,
    get_ebay_product_data,
    get_amazon_product_data,
)


links = [
    # Mens
    ["SHOES", "https://etnies.com/collections/mens-shoes", "Male","Mens"],
    ["Shirts", "https://etnies.com/collections/shirts", "Male","Mens"],
    ["Jackets", "https://etnies.com/collections/jackets", "Male","Mens"],
    ["Pants/Denim", "https://etnies.com/collections/pants-1", "Male","Mens"],
    ["Apparel", "https://etnies.com/collections/mtb-apparel", "Male","Mens"],
    ["TEES", "https://etnies.com/collections/tees", "Male","Mens"],
    ["SWEATSHIRTS", "https://etnies.com/collections/sweatshirts", "Male","Mens"],
    ["SOCKS", "https://etnies.com/collections/socks", "Male","Mens"],
    ["HATS", "https://etnies.com/collections/hats", "Male","Mens"],
    ["BEANIES", "https://etnies.com/collections/beanies", "Male","Mens"],
    ["BACKPACKS", "https://etnies.com/collections/backpacks", "Male","Mens"],
    # Women
    # Kids
    ["SHOES", "https://etnies.com/collections/kids-shoes", "Male","Kids"],
    ["APPAREL", "https://etnies.com/collections/kids-apparel", "Male","Kids"],
]

skus = []
product_links = []
products_data = []
reviews_data = []


def write_file(file_name, content):
    with open(f"{file_name}.html", "w", encoding="utf-8") as file:
        file.write(str(content))


# def correct_link(l:str):
#     if l.find("/collections/")!=-1:
#         l=l.replace("/collections/","")
#         idx=l.find("/")
#         if idx!=-1:
#             l=l[idx:]
#     return l
def get_category_product_links(item):
    link = item[1]

    category_product_links = []
    try:
        count = 1
        while count != -1:
            params = {
                "page": str(count),
            }
            resp = requests.get(link, params=params)
            soup = BeautifulSoup(resp.content, "html.parser")
            con_ls = soup.find_all("div", class_="product__imageContainer")
            for con in con_ls:
                # p_link=correct_link(con.find("a")["href"])
                p_link = "https://etnies.com{0}".format(con.find("a")["href"])
                if p_link in product_links:
                    continue
                product_links.append(p_link)
                # print(item)
                dct = {
                    "Link": p_link,
                    "Standardized Product Type": item[5],
                    "Custom Product Type": item[6],
                    "WEIGHT GRAMS": item[7],
                    "Gender": item[2],
                    "Title Gender":item[3]
                }
                category_product_links.append(dct)
            count += 1
            if len(con_ls) == 0:
                count = -1
    except Exception as exc:
        print(exc)
    return category_product_links


def get_product_types():
    product_type_links = []
    df = pd.read_excel("Etnies_Lookup_Table.xlsx")
    for link in links:
        for type in df.values.tolist():
            if type[0].lower() == link[0].lower():
                product_type_links.append(link + type)
                break
    return product_type_links


def get_driver():
    # chrome_options = webdriver.ChromeOptions()
    # # driver_service = Service(driver_path)
    # return webdriver.Chrome(service=driver_service, options=chrome_options)

    return webdriver.Chrome()


def correct_link(main_link: str, link: str):
    idx1 = main_link.find("/products/")
    idx2 = link.find("/products/")
    if idx1 != -1 and idx2 != -1:
        link = main_link[:idx1] + link[idx2:]
    return link


def extract_product_info(page_source, link):
    soup = BeautifulSoup(page_source, "html.parser")
    # write_file('temp', soup.prettify())
    # try:
    #     if soup.find("span", class_="savings").find("span"):
    #         print("Item on sale -> ", link)
    # except:
    #     pass
    js = None
    match = re.search(
        r"window.SwymProductInfo.product = ({.*?});", page_source, re.DOTALL
    )
    # match = re.search(r'const product = ({.*?});', page_source, re.DOTALL)
    if match:
        product_pricing_data = match.group(1)
        # Load the extracted data into a JSON object
        js = json.loads(product_pricing_data)
    else:
        print("Error -> ", link)
        return

    def get_reviews():
        reviews = []
        dt = {}
        for div in soup.find_all("div", class_="jdgm-divider-top"):
            dt["Author"] = div.find("span", class_="jdgm-rev__author").text
            dt["Title"] = div.find("b", class_="jdgm-rev__title").text
            dt["Body"] = div.find("div", class_="jdgm-rev__body").text
            dt["Created At"] = div.find("span", class_="jdgm-rev__timestamp").text
            dt["Rating"] = div.find("span", class_="jdgm-rev__rating")["data-score"]
            reviews.append(dt.copy())
        return reviews

    def get_variants():
        variants = []
        for var in js["variants"]:
            variants.append(
                {
                    "Barcode": var["barcode"],
                    "Sku": var["sku"],
                    "Color": var["option1"],
                    "Size": var["option2"],
                    "Quantity": var["available"],
                }
            )
        return variants

    def get_color_ways():
        color_ways = []
        cont = soup.find("ul", class_="swatch-view-image")
        if not cont:
            return color_ways
        for div in cont.find_all("div", class_="swatch-group-selector"):
            url = correct_link(link, div["swatch-url"])
            if url not in product_links:
                color_ways.append(url)
        return color_ways

    price = str(js["price"])
    price = price.rsplit("99", 1)[0] + ".99"
    images = js["images"]
    for i in range(len(images)):
        images[i] = images[i].replace("//", "https://")
    description = js["description"]
    return {
        "Title": js["title"],
        "Handle": js["handle"],
        "Price": price,
        "Description": description,
        "Variants": get_variants(),
        "ColorWays": get_color_ways(),
        "Reviews": get_reviews(),
        "Images": images,
    }


def add_prod_info(prod_info, prod_data: dict):
    prod_data.update(prod_info)
    raw_data.append(prod_data)
    image_list = prod_data["Images"]
    description = prod_data["Description"]
    current_variant = prod_data["Variants"][0]
    sku, color = current_variant["Sku"], current_variant["Color"]
    color = color.replace("/", " ").title()
    color_code = extract_style_code(image_list, sku)
    sku = f"{sku}-{color_code}"
    size = current_variant["Size"]
    style = prod_data["Title"].title()  # name of product
    item_type = prod_data["Custom Product Type"]  # what is product
    gender = prod_data["Gender"]
    item_type_s = item_type
    # if item_type!="Shoes" and item_type!="Socks" and item_type!="Pants":
    item_type_s = singularize(item_type)
    style = style.replace(item_type_s, "")
    # brand + gender + style + color + item type
    title = f"Etnies {gender} {style} {color} {item_type_s}"
    title = (
        title.title()
        .replace("Kids", "Boys")
        .replace("Male", "Mens")
        .replace("Female", "Womens")
    )
    if "Boys" in title and "Mens" in title:
        title = title.replace("Mens ", "")
    for v in [["Shoes", "Shoe"], ["Socks", "Sock"], ["Pants", "Pant"]]:
        if v[1] in title and not v[0] in title:
            title = title.replace(v[1], v[0])
            break
    title = remove_double_spaces(title)
    title=title.replace("-","")
    if "Boys" in title:
        title = switch_words(title)
    # handle = f"{sku}-{color}"
    price = prod_data["Price"]
    # print(title,sku)
    handle=f'{title} {sku}'
    # print(handle)
    handle=remove_double_spaces(handle)
    handle=handle.lower().replace(' ', '-')
    # print(handle)
    if handle in skus:
        print("Duplicate Sku")
        return
    skus.append(handle)

    new_dt = {
        "handle": handle,
        "new_title": title,
        "url": "",
        "title": prod_data["Title"],
        "images": image_list,
        "description": description,
        "gender": {
            "gender": prod_data["Gender"],
            "age_group": "adult",
            "title_gender": prod_data["Title Gender"],
        },
        "type": item_type_s,
        "type_p": item_type,
        "color": color,
        "style_code": color_code,
        "price": price,
        "cost": getPrice(price) / 2,
        "features": [],
        "bullet_points": [],
        "widths": "",
        "category": prod_data["Standardized Product Type"],
        "weight": prod_data["WEIGHT GRAMS"],
        "stock": [],
        "sizes": [],
    }
    for var in prod_data["Variants"]:
        size = var["Size"]
        qty = var["Quantity"]
        if qty:
            qty = "4"
        else:
            qty = 0
        new_dt["stock"].append(
            {
                "SKU": f"{sku}-{size}",
                "Quantity": qty,
                "Upc": var["Barcode"],
                "size": size,
                "code": sku,
            }
        )
        new_dt["sizes"].append(size)

    products_data.append(new_dt.copy())

    for row in prod_data["Reviews"]:
        rev = {
            "product_handle": handle,
            "state": "published",
            "rating": row["Rating"],
            "title": row["Title"],
            "author": row["Author"],
            "email": "",
            "body": row["Body"],
            "created_at": row["Created At"],
        }
        duplicate = False
        for l in reviews_data:
            if l["author"] == rev["author"] and l["body"] == rev["body"]:
                duplicate = True
                break
        if not duplicate:
            reviews_data.append(rev.copy())



def scrap_product(driver, link):
    driver.get(link)
    driver.implicitly_wait(20)
    return extract_product_info(driver.page_source, link)


raw_data = []


def scrap_site():
    try:
        p_links = []
        for v in get_product_types():
            p_links.extend(get_category_product_links(v))
            # break
        print("Links ->", len(p_links))
        # return
        # p_links = p_links[:25]
        driver = get_driver()
        for p in p_links:
            try:
                prod_data = scrap_product(driver, p["Link"])
                if prod_data:
                    add_prod_info(p, prod_data)
            except:
                traceback.print_exc()
            # break
    except:
        traceback.print_exc()


def read_existing_data():
    df = pd.read_excel("output_raw.xlsx")
    df["Price"] = df["Price"].fillna("")
    df["Price"] = df["Price"].astype(str)
    df["Variants"] = df["Variants"].apply(ast.literal_eval)
    df["Reviews"] = df["Reviews"].apply(ast.literal_eval)
    df["Images"] = df["Images"].apply(ast.literal_eval)
    # df['widths'] = df['widths'].fillna("")
    for index, row in df.iterrows():
        dt = row.to_dict()
        add_prod_info({}, dt)


def main():
    # read_existing_data()
    scrap_site()
    pd.DataFrame(raw_data).to_excel("output_raw.xlsx",index=False)
    # return
    file_path = "Template.xlsx"  # Replace with the path to your existing Excel file
    workbook = openpyxl.load_workbook(file_path)
    vendor = "Etnies"
    get_shopify_product_data(products_data, vendor, workbook)
    get_ebay_product_data(products_data, vendor, workbook)
    get_walmart_product_data(products_data,vendor,workbook)
    get_amazon_product_data(products_data,vendor,workbook)

    current_date = datetime.now().strftime("%Y-%m-%d")
    workbook.save(f"{vendor}_{current_date}.xlsx")
    workbook.close()

    current_date = datetime.now().strftime("%d %b %y")
    output_file = f"Reviews {current_date} - Etnies.xlsx"

    df2=pd.DataFrame(reviews_data)
    df2 = df2.drop_duplicates()
    with pd.ExcelWriter(output_file) as writer:
        df2.to_excel(writer, sheet_name='Reviews',index=False)


if __name__ == "__main__":
    main()
