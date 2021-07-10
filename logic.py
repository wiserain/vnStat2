# -*- coding: utf-8 -*-
import os
import traceback
from datetime import datetime
import subprocess
import json
import platform

# third-party
from flask import render_template, jsonify

# app common
from framework import app
from framework.common.plugin import LogicModuleBase
from system.logic_command2 import SystemLogicCommand2 as SystemCommand

# local
from .plugin import plugin

logger = plugin.logger
package_name = plugin.package_name
plugin_info = plugin.plugin_info
ModelSetting = plugin.ModelSetting


def strftime(dt, fmt):
    year = dt['date']['year'] if ('date' in dt and 'year' in dt['date']) else 1971
    month = dt['date']['month'] if ('date' in dt and 'month' in dt['date']) else 1
    day = dt['date']['day'] if ('date' in dt and 'day' in dt['date']) else 1
    hour = dt['time']['hour'] if ('time' in dt and 'hour' in dt['time']) else 0
    minute = dt['time']['minute'] if ('time' in dt and 'minute' in dt['time']) else 0
    return datetime(year, month, day, hour, minute).strftime(fmt)


class LogicMain(LogicModuleBase):
    db_default = {
        'interval': '20',
        'default_interface_id': '',
        'default_traffic_view': '3',
        'traffic_unit': '1',
        'traffic_list': '24,24,30,12,0,10'
    }
    
    def __init__(self, P):
        super(LogicMain, self).__init__(P, None)

    def plugin_load(self):
        try:
            # vnstat 자동설치
            is_installed = self.is_installed()
            if not is_installed or not any(x in is_installed for x in plugin_info['supported_vnstat_version']):
                self.install(show_modal=False)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    def process_menu(self, sub, req):
        arg = ModelSetting.to_dict()
        if sub == 'setting':
            return render_template(f'{package_name}_{sub}.html', sub=sub, arg=arg)
        elif sub == 'traffic':
            return render_template(f'{package_name}_{sub}.html', arg=arg)
        return render_template('sample.html', title=f'{package_name} - {sub}')

    def process_ajax(self, sub, req):
        if sub == 'install':
            try:
                ret = self.install()
                return jsonify(ret)
            except Exception as e: 
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
        elif sub == 'is_installed':
            try:
                is_installed = self.is_installed()
                if is_installed:
                    ret = {'installed': True, 'version': is_installed}
                else:
                    ret = {'installed': False}
                return jsonify(ret)
            except Exception as e:
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
        elif sub == 'get_default_interface_id':
            try:
                return jsonify({'default_interface_id': ModelSetting.get('default_interface_id')})
            except Exception as e: 
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
        elif sub == 'get_vnstat_info':
            try:
                ret = self.get_vnstat_info()
                return jsonify(ret)
            except Exception as e:
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())

    def is_installed(self):
        try:
            verstr = subprocess.check_output("vnstat -v", shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
            vernum = verstr.split()[1]
            if not any(vernum in x for x in plugin_info['supported_vnstat_version']):
                vernum += ' - 지원하지 않는 버전'
            return vernum
        except Exception:
            return False

    def install(self, show_modal=True):
        try:
            if platform.system() == 'Linux' and app.config['config']['running_type'] == 'docker':
                install_sh = os.path.join(os.path.dirname(__file__), 'install.sh')                
                commands = [
                    ['msg', u'잠시만 기다려주세요.'],
                    ['chmod', '+x', install_sh],
                    [install_sh, '2.6'],
                    ['msg', u'완료되었습니다.']
                ]
                SystemCommand('vnStat 설치', commands, wait=True, show_modal=show_modal, clear=True).start()
                return {'success': True}
            else:
                return {'succes': False, 'log': '지원하지 않는 시스템입니다.'}
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return {'success': False, 'log': str(e)}

    def parsing_vnstat_traffic(self, traffic, data_type):
        labels, rxs, txs, totals = [], [], [], []
        for item in traffic[data_type]:
            # fiveminute, hour, day, month, year, top
            if data_type == 'fiveminute':
                label = strftime(item, '%H:%M')
                if label == '00:00':
                    label = strftime(item, '%-d일 ') + label
            elif data_type == 'hour':
                label = strftime(item, '%-H시')
                if label == '0시':
                    label = strftime(item, '%-d일 ') + label
            elif data_type == 'day':
                label = strftime(item, '%-d일')
                if label == '1일':
                    label = strftime(item, '%-m월 ') + label
            elif data_type == 'month':
                label = strftime(item, '%-m월')
                if label == '1월':
                    label = strftime(item, '%y년 ') + label
            elif data_type == 'year':
                label = strftime(item, '%Y년')
            elif data_type == 'top':
                label = strftime(item, '%Y-%m-%d')
            labels.append(label)
            rxs.append(item['rx'])
            txs.append(item['tx'])
            totals.append((item['rx']+item['tx']))
        return {
            'labels': labels,
            'rxs': rxs,
            'txs': txs,
            'totals': totals,
        }

    def parsing_vnstat_json(self, vnstat_json):
        ret = []
        for interface in vnstat_json['interfaces']:
            traffic = interface['traffic']
            vnstat_interfaces = {
                'name': interface['name'],
                'created': strftime(interface['created'], '%Y-%m-%d'),
                'updated': strftime(interface['updated'], '%Y-%m-%d %H:%M'),
                'fiveminute': self.parsing_vnstat_traffic(traffic, 'fiveminute'),
                'hour': self.parsing_vnstat_traffic(traffic, 'hour'),
                'day': self.parsing_vnstat_traffic(traffic, 'day'),
                'month': self.parsing_vnstat_traffic(traffic, 'month'),
                'year': self.parsing_vnstat_traffic(traffic, 'year'),
                'top': self.parsing_vnstat_traffic(traffic, 'top'),
            }
            # summary
            labels, rxs, txs, totals = [], [], [], []
            
            labels.append('오늘')
            rxs.append(vnstat_interfaces['day']['rxs'][-1])
            txs.append(vnstat_interfaces['day']['txs'][-1])
            totals.append(vnstat_interfaces['day']['totals'][-1])
            
            labels.append('이번달')
            rxs.append(vnstat_interfaces['month']['rxs'][-1])
            txs.append(vnstat_interfaces['month']['txs'][-1])
            totals.append(vnstat_interfaces['month']['totals'][-1])
            
            labels.append('전체기간')
            rxs.append(traffic['total']['rx'])
            txs.append(traffic['total']['tx'])
            totals.append((traffic['total']['rx']+traffic['total']['tx']))

            vnstat_interfaces.update({'summary': {
                'labels': labels,
                'rxs': rxs,
                'txs': txs,
                'totals': totals,
            }})

            # limit
            tf_view_keys = ['fiveminute', 'hour', 'day', 'month', 'year', 'top']
            tf_list_vals = [x.strip() for x in ModelSetting.get('traffic_list').split(',')]
            for key, val in zip(tf_view_keys, tf_list_vals):
                nlimit = int(val) if val.isdigit() else 0
                for subkey in ['labels', 'rxs', 'txs', 'totals']:
                    vnstat_interfaces[key][subkey] = vnstat_interfaces[key][subkey][-nlimit:]

            ret.append(vnstat_interfaces)
        return ret

    def get_vnstat_info(self):
        try:
            vnstat_stdout = subprocess.check_output("vnstat --json", shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
            vnstat_json = json.loads(vnstat_stdout)
            try:
                vnstat_info = self.parsing_vnstat_json(vnstat_json)
                return {'ret': 'success', 'data': vnstat_info}
            except Exception as e:
                logger.error('Exception: %s', e)
                return {'ret': 'parsing_error', 'log': str(e)}
        except subprocess.CalledProcessError as e:
            # vnStat 바이너리가 없을때
            logger.error('Exception:%s', e.output.strip())
            return {'ret': 'no_bin', 'log': e.output.strip().decode('utf-8')}
        except Exception as e:
            # 그 외의 에러, 대부분 데이터베이스가 없어서 json 값이 들어오지 않는 경우
            logger.error('Exception:%s', e)
            return {'ret': 'no_json', 'log': vnstat_stdout}
