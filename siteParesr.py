import textwrap

import numpy as np
import requests
from bs4 import BeautifulSoup
import pandas as pd
import dataframe_image as dfi


class Parser:
    url = "https://timetable.xn--b1ahgiuw.xn--p1ai/student/"

    def __init__(self):
        self.response = None
        self.soup = None
        self.links = {}

    def get_current_data(self):
        self.response = requests.get(self.url)
        if self.response.status_code == 200:
            self.soup = BeautifulSoup(self.response.content, 'html.parser')
            return self.response
        else:
            return None

    def parse_table_links(self):
        if not self.soup:
            self.get_current_data()

        if self.soup:
            self.links.clear()
            table = self.soup.find('table')
            if table:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip the header row
                    cells = row.find_all('td')
                    for cell in cells:
                        link = cell.find('a')
                        if link:
                            group_name = link.text.strip().lower()
                            href = link.get('href')
                            self.links[group_name] = href

    def get_group_links(self, name, force=False):
        if len(self.links) == 0 or force:
            self.parse_table_links()
        return self.links.get(name.lower(), None)

    def get_schedule_table(self, group_link, current_week):
        response = requests.get(self.url + group_link)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            body = soup.find('body')
            table = body.find_all('table')
            fonts = body.find_all("font", recursive=False)
            if current_week:
                table = table[0]
                res_fonts = [f.get_text() for f in fonts[:3]]
            else:
                table = table[1]  # Skip the header row
                splited = fonts[4].get_text().strip().split()
                res_fonts = [fonts[3].get_text(), splited[0], splited[1] + " " + splited[2]]
            return table, res_fonts
        return None

    def table_to_image(self, table, output_file, titles=["Shedule", "1"]):
        df = pd.read_html(str(table))[0]
        df.replace(np.nan, '', inplace=True)

        # df = df.applymap(lambda x: textwrap.fill(x, width=30) if isinstance(x, str) else x)
        df.iloc[1:, 1:] = df.iloc[1:, 1:].applymap(lambda x: textwrap.fill(x, width=20) if isinstance(x, str) else x)

        # Add a title, hide both index and column headers, center text, and add borders
        caption_html = f"""
                <div style='display: flex; justify-content: space-between; font-size: 20px;'>
                    <p style='text-align: left;'>{titles[0]}<span style='color:red;'> {titles[1]}</span></p>
                    <p style='text-align: center;'>t.me/ulstu_shedule_bot</p>
                    <p style='text-align: right;'>{titles[2]}</p>
                </div>
                """
        styled_df = (df.style.set_caption(caption_html).hide(axis='index').hide(axis='columns')
        .hide(axis='columns',
              subset=df.columns[
                  -1]).set_properties(
            **{
                'white-space': 'pre-wrap',  # Preserve whitespace and wrap text
                'overflow-wrap': 'break-word',  # Break long words
                'text-align': 'center'  # Center the text
            }).set_table_styles([
            {"selector": "td, th", "props": [("border", "1px solid grey !important")]},
            {"selector": "caption", "props": [("caption-side", "top"), ("text-align", "center"), ("font-size", "16px"),
                                              ("font-weight", "bold")]}
        ]))

        dfi.export(styled_df, output_file, dpi=100, table_conversion='selenium')
        return True

    def get_schedule_image(self, group_name, current_week: bool, output_file):
        group_link = self.get_group_links(group_name)
        if group_link:
            table, titles = self.get_schedule_table(group_link, current_week)
            if table:
                return self.table_to_image(table, output_file, titles=titles), titles
        return False
