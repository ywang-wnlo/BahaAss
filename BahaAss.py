import re
import json

import requests

template_ass = '''[Script Info]
Title: {}
Original Script: BahaAss.py
ScriptType: v4.00+
Collisions: Normal
PlayResY: 1080
PlayResX: 1920
WrapStyle: 0

[v4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: DefaultStyle,Microsoft YaHei UI,50,&H80FFFFFF,&H80FFFFFF,&H80000000,&H80000000,-1,0,0,0,100,100,0,0,1,1,0,5,0,0,0,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'''


class BahaAss(object):
    def __init__(self):
        self._headers = {
            'Host': None,
            'Referer': None,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        }
        self._sn_list = []
        self._sn_dict = {}
        self._digits_num = None
        self._title = None

    def _get_all_sn(self, base_url):
        base_response = requests.get(base_url, headers=self._headers)
        # with open('base.html', 'wb') as fp:
        #     fp.write(base_response.content)
        base_response.encoding = 'utf8'

        sn_list = re.findall(
            r'<a href=\"\?sn=(\d+)\">(\S+)</a>', base_response.text)
        _max = 0
        for sn in sn_list:
            self._sn_list.append(sn[0])
            self._sn_dict[sn[0]] = int(sn[1])
            _max = max(_max, int(sn[1]))
        self._digits_num = len(str(_max))

        h1_list = re.findall(
            r'<h1>(\S+) \[\d+\]</h1>', base_response.text)
        self._title = h1_list[0]

    def _get_danmu(self, sn) -> dict:
        danmu_url = 'https://ani.gamer.com.tw/ajax/danmuGet.php'
        danmu_data = {'sn': sn}
        danmu_response = requests.post(
            danmu_url, danmu_data, headers=self._headers)

        danmu_json = json.loads(danmu_response.content)
        # with open('danmu.json', 'w') as fp:
        #     json.dump(danmu_json, fp, ensure_ascii=False, indent='\t')
        return danmu_json

    def _time_str(self, time: int) -> str:
        second = time // 10
        minute = second // 60
        hour = minute // 60

        hour_str = str(hour)
        minute_str = str(minute - 60 * hour)
        second_str = str(second - 60 * minute) + '.' + str(time)[-1] + '0'

        return f'{hour_str}:{minute_str}:{second_str}'

    # TODO 通过独立函数 get_pos_y 获取最佳 y 值

    def _parse_danmu(self, danmu: dict, sn: str):
        title = '{}_{}'.format(self._title, str(
            self._sn_dict[sn]).zfill(self._digits_num))
        with open(f'{title}.ass', 'w') as fp:
            # text 弹幕内容
            # color #RGB值
            # size 0->小 1->正常 2->大
            # position 0->滚动 1->上方 2->下方
            # time 0.1s
            y1 = 25
            y2 = 25
            y3 = 25
            t1 = 0
            t2 = 0
            t3 = 0
            fp.write(template_ass.format(title))
            for one_dict in danmu:
                start_time = one_dict['time']
                start_time_str = self._time_str(start_time)
                end_time = start_time + 50  # 默认 5s
                end_time_str = self._time_str(end_time)
                # \pos(<x>, <y>)
                # \move(<x1>, <y1>, <x2>, <y2>)
                # \c&H<bbggrr>&
                if one_dict['position'] == 0:
                    if start_time < t1:
                        y1 += 50
                        y1 = y1 % 400
                    else:
                        y1 = 25
                    t1 = end_time
                    style = f'{{\move(1920,{y1},0,{y1})'
                elif one_dict['position'] == 1:
                    if start_time < t2:
                        y2 += 50
                        y2 = y2 % 400
                    else:
                        y2 = 25
                    t2 = end_time
                    style = f'{{\pos(960,{y2})'
                else:
                    if start_time < t3:
                        y3 += 50
                        y3 = y3 % 400
                    else:
                        y3 = 25
                    t3 = end_time
                    style = f'{{\pos(960,{1080-y3})'
                style += '\c&H' + one_dict['color'][1:] + '&}'
                text = one_dict['text'].strip()
                fp.write('\nDialogue: 0,{},{},DefaultStyle,,0,0,0,,{}{}'.format(
                    start_time_str, end_time_str, style, text))

    def run(self):
        base_url = 'https://ani.gamer.com.tw/animeVideo.php?sn=20219'
        self._get_all_sn(base_url)
        for sn in self._sn_list:
            danmu = self._get_danmu(sn)
            self._parse_danmu(danmu, sn)
            break  # TODO


if __name__ == '__main__':
    baha_ass = BahaAss()
    baha_ass.run()
