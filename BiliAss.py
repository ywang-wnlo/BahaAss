import json
import time
import random

import google.protobuf.json_format as json_format
import dm_pb2 as Danmaku
import requests

# https://cnfczn.com/article/ass%E5%AD%97%E5%B9%95%E6%A0%BC%E5%BC%8F%E8%AF%A6%E8%A7%A3
# http://www.perlfu.co.uk/projects/asa/ass-specs.doc
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
Style: DefaultStyle,Microsoft YaHei UI,{},&H80FFFFFF,&H80FFFFFF,&H80000000,&H80000000,-1,0,0,0,100,100,0,0,1,1,0,5,0,0,0,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'''


class BiliAss(object):
    def __init__(self):
        self._headers = {
            'Host': None,
            'Referer': None,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        }
        self._ep_list = []
        self._ep_dict = {}
        self._digits_num = None
        self._title = None
        self._font_size = 40
        self._pos_end_time = [[], []]
        self._pos_time = 5000  # 上下弹幕默认 5s
        self._move_start_time = []
        self._move_text_len = []
        self._move_time = 10000  # 滚动弹幕默认 10s
        for i in range(1080 // self._font_size):
            self._pos_end_time[0].append(-1)
            self._pos_end_time[1].append(-1)
            self._move_start_time.append(-self._move_time)
            self._move_text_len.append(0)

    def _reset_aux_vars(self):
        for i in range(1080 // self._font_size):
            self._pos_end_time[0][i] = -1
            self._pos_end_time[1][i] = -1
            self._move_start_time[i] = -self._move_time
            self._move_text_len[i] = 0

    def _get_all_ep(self, ep_url):
        base_response = requests.get(ep_url, headers=self._headers)
        bash_json = json.loads(base_response.content)
        # with open('base.json', 'w', encoding='utf8') as fp:
        #     json.dump(bash_json, fp, ensure_ascii=False, indent='\t')
        episodes = bash_json['result']['episodes']

        _max = 0
        for episode in episodes:
            self._ep_list.append(episode['id'])
            self._ep_dict[episode['id']] = {
                'title': episode['title'],
                'long_title': episode['long_title'],
                'link': episode['link'],
                'aid': episode['aid'],
                'cid': episode['cid'],
                'bvid': episode['bvid'],
                'duration': int(episode['duration']),
            }
            _max = max(_max, int(episode['title']))
        self._digits_num = len(str(_max))

        self._title = bash_json['result']['title']

    def _get_danmu(self, ep) -> list:
        danmu_url = 'http://api.bilibili.com/x/v2/dm/web/seg.so'
        params = {
            'type': 1,  # 弹幕类型
            'oid': self._ep_dict[ep]['cid'],  # cid
            'pid': self._ep_dict[ep]['aid'],  # avid
            'segment_index': 1  # 弹幕分段
        }

        danmu_list = []
        duration = self._ep_dict[ep]['duration']
        while duration > 0:
            danmu_response = requests.get(
                danmu_url, params, headers=self._headers)
            data = danmu_response.content

            danmaku_seg = Danmaku.DmSegMobileReply()
            danmaku_seg.ParseFromString(data)

            for elem in danmaku_seg.elems:
                one_dict = json_format.MessageToDict(elem)
                if 'progress' not in one_dict:
                    continue
                danmu_list.append(one_dict)
            duration -= 360000  # 每段 6 min
            params['segment_index'] += 1

        danmu_list.sort(key=lambda d: d['progress'])   # 根据时间重新排序
        return danmu_list

    def _time_str(self, time: int) -> str:
        second = time // 1000
        minute = second // 60
        hour = minute // 60

        hour_str = str(hour)
        minute_str = str(minute - 60 * hour)
        second_str = str(second - 60 * minute) + '.' + str(time % 1000)[:2]

        return f'{hour_str}:{minute_str}:{second_str}'

    def _get_pos_str(self, start_time: int, position: int) -> str:
        # \pos(<x>, <y>)
        pos_str = '\pos(960,{})'
        index = position - 4
        y = None

        min_end_time = self._pos_end_time[index][0]
        min_i = 0
        for i in range(len(self._pos_end_time[index])):
            if position == 4 and i < 0.1 * len(self._pos_end_time[index]):
                # 底部弹幕预留 10%
                min_end_time = self._pos_end_time[index][i + 1]
                min_i = i + 1
                continue
            end_time = self._pos_end_time[index][i]
            if start_time > end_time:
                y = i * self._font_size + (self._font_size + 1) // 2
                self._pos_end_time[index][i] = start_time + self._pos_time
                break
            if end_time < min_end_time:
                min_end_time = end_time
                min_i = i

        if y is None:
            y = min_i * self._font_size + (self._font_size + 1) // 2
            self._pos_end_time[index][min_i] = start_time + self._pos_time
            print(f'警告：{self._time_str(start_time)} 时上下方弹幕过密，会有重叠')

        if position == 5:
            pos_str = pos_str.format(y)
        else:
            pos_str = pos_str.format(1080 - y)
        return pos_str

    def _not_overlap(self, start_time1: int, text_len1: int, start_time2: int, text_len2: int) -> bool:
        if start_time2 > start_time1 + self._move_time:
            # 上一个弹幕已结束
            return True
        else:
            # 弹幕长度
            l1 = text_len1 * self._font_size
            l2 = text_len2 * self._font_size
            # 弹幕速度
            v1 = (1920 + l1) / self._move_time
            v2 = (1920 + l2) / self._move_time
            # 间隔时间
            delta_time = start_time2 - start_time1
            # 弹幕间隔
            delta_l = 4 * self._font_size
            if v1 * delta_time <= l1 + delta_l:
                # 新的出发时，保证上一个已完全出去，并由足够间隔
                return False
            if v2 * (self._move_time - delta_time) >= 1920 - delta_l:
                # 上个到达时，保证新的也于其有足够间隔
                return False
        return True

    def _get_move_str(self, start_time: int, text_len: int) -> str:
        # \move(<x1>, <y1>, <x2>, <y2>)
        move_str = '\move({},{},{},{})'
        x = text_len * self._font_size // 2
        y = None

        min_i = 0
        min_start_time = self._move_start_time[0]
        for i in range(len(self._move_start_time)):
            if self._not_overlap(self._move_start_time[i], self._move_text_len[i], start_time, text_len):
                y = i * self._font_size + (self._font_size + 1) // 2
                self._move_start_time[i] = start_time
                self._move_text_len[i] = text_len
                break
            if self._move_start_time[i] < min_start_time:
                min_start_time = self._move_start_time[i]
                min_i = i

        if y is None:
            y = min_i * self._font_size + (self._font_size + 1) // 2
            self._move_start_time[min_i] = start_time
            self._move_text_len[min_i] = text_len
            print(f'警告：{self._time_str(start_time)} 时滚动弹幕过密，可能会有重叠')

        return move_str.format(1920+x, y, 0-x, y)

    def _parse_danmu(self, danmu: list, ep: str):
        title = '{}_{}_{}'.format(self._title, str(
            self._ep_dict[ep]['title']).zfill(self._digits_num), self._ep_dict[ep]['long_title'])
        with open(f'{title}.ass', 'w', encoding='utf8') as fp:
            # content 弹幕内容
            # color 十进制RGB值
            # mode 123->滚动 4->下方 5->上方
            # progress ms
            y1 = 25
            t1 = 0
            fp.write(template_ass.format(title, self._font_size))
            for one_dict in danmu:
                start_time = one_dict['progress']
                position = one_dict['mode']
                color = one_dict['color']
                # \c&H<bbggrr>&
                color_str = '\c&H{}&'.format(str(hex(color)).upper()[2:])
                text = one_dict['content']

                if (position == 1) or (position == 2) or (position == 3):
                    end_time = start_time + self._move_time
                    move_str = self._get_move_str(start_time, len(text))
                    style = f'{move_str}{color_str}'
                else:
                    end_time = start_time + self._pos_time
                    end_time_str = self._time_str(end_time)
                    pos_str = self._get_pos_str(start_time, position)
                    style = f'{pos_str}{color_str}'

                start_time_str = self._time_str(start_time)
                end_time_str = self._time_str(end_time)

                fp.write('\nDialogue: 0,{},{},DefaultStyle,,0,0,0,,{{{}}}{}'.format(
                    start_time_str, end_time_str, style, text))

    def run(self, ep_id):
        ep_url = f'https://api.bilibili.com/pgc/view/web/season?ep_id={ep_id}'
        self._get_all_ep(ep_url)
        for ep in self._ep_list:
            self._reset_aux_vars()
            danmu = self._get_danmu(ep)
            self._parse_danmu(danmu, ep)
            print(
                f"{self._title} [{self._ep_dict[ep]['title']}][{self._ep_dict[ep]['long_title']}] 已转换成功! 为防止被 ban，休眠中……")
            time.sleep(random.uniform(5, 10))


if __name__ == '__main__':
    bili_ass = BiliAss()
    bili_ass.run(input('输入 ep 号：'))
