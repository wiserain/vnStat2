# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
from datetime import datetime
import subprocess
import json

# third-party

# sjva 공용
from framework import db, scheduler, app
from framework.job import Job
from framework.util import Util


# 패키지
from .plugin import package_name, logger
from .model import ModelSetting


def strftime(dt, fmt):
    year = dt['date']['year'] if ('date' in dt and 'year' in dt['date']) else 1971
    month = dt['date']['month'] if ('date' in dt and 'month' in dt['date']) else 1
    day = dt['date']['day'] if ('date' in dt and 'day' in dt['date']) else 1
    hour = dt['time']['hour'] if ('time' in dt and 'hour' in dt['time']) else 0
    minute = dt['time']['minute'] if ('time' in dt and 'minute' in dt['time']) else 0
    return datetime(year, month, day, hour, minute).strftime(fmt)


class Logic(object):
    # 디폴트 세팅값
    db_default = {
        'interval': '20',
        'default_interface_id': '',
        'default_traffic_view': '3',
        'traffic_unit': '1',
        'traffic_list': '24,24,30,12,0,10'
    }

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_load():
        try:
            logger.debug('%s plugin_load', package_name)
            # DB 초기화
            Logic.db_init()

            # 편의를 위해 json 파일 생성
            from .plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))

            # vnstat 자동설치
            is_installed = Logic.is_installed()
            if not is_installed or not any(x in is_installed for x in plugin_info['supported_vnstat_version']):
                Logic.install()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def setting_save(req):
        try:
            for key, value in req.form.items():
                entity = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
                entity.value = value
            db.session.commit()
            return True                  
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False
    # 기본 구조 End
    ##################################################################

    @staticmethod
    def is_installed():
        try:
            verstr = subprocess.check_output("vnstat -v", shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
            vernum = verstr.split()[1]
            from .plugin import plugin_info
            if not any(vernum in x for x in plugin_info['supported_vnstat_version']):
                vernum += ' - 지원하지 않는 버전'
            return vernum
        except Exception:
            return False

    @staticmethod
    def install():
        try:
            import platform, threading
            if platform.system() == 'Linux' and app.config['config']['running_type'] == 'docker':
                install_sh = os.path.join(os.path.dirname(__file__), 'install.sh')
                def func():
                    import system
                    commands = [
                        ['msg', u'잠시만 기다려주세요.'],
                        ['chmod', '+x', install_sh],
                        [install_sh, '2.6'],
                        ['msg', u'설치가 완료되었습니다.']
                    ]
                    system.SystemLogicCommand.start('설치', commands)
                t = threading.Thread(target=func, args=())
                t.setDaemon(True)
                t.start()
                return {'success': True}
            else:
                return {'succes': False, 'log': '지원하지 않는 시스템입니다.'}
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return {'success': False, 'log': str(e)}

    @staticmethod
    def parsing_vnstat_traffic(traffic, data_type):
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
    
    @staticmethod
    def parsing_vnstat_json(vnstat_json):
        ret = []
        for interface in vnstat_json['interfaces']:
            traffic = interface['traffic']
            vnstat_interfaces = {
                'name': interface['name'],
                'created': strftime(interface['created'], '%Y-%m-%d'),
                'updated': strftime(interface['updated'], '%Y-%m-%d %H:%M'),
                'fiveminute': Logic.parsing_vnstat_traffic(traffic, 'fiveminute'),
                'hour': Logic.parsing_vnstat_traffic(traffic, 'hour'),
                'day': Logic.parsing_vnstat_traffic(traffic, 'day'),
                'month': Logic.parsing_vnstat_traffic(traffic, 'month'),
                'year': Logic.parsing_vnstat_traffic(traffic, 'year'),
                'top': Logic.parsing_vnstat_traffic(traffic, 'top'),
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

    @staticmethod
    def get_vnstat_info():
        try:
            vnstat_stdout = subprocess.check_output("vnstat --json", shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
            vnstat_json = json.loads(vnstat_stdout)
            try:
                vnstat_info = Logic.parsing_vnstat_json(vnstat_json)
                return {'ret': 'success', 'data': vnstat_info}
            except Exception as e:
                logger.error('Exception: %s', e)
                return {'ret': 'parsing_error', 'log': str(e)}
        except subprocess.CalledProcessError as e:
            # vnStat 바이너리가 없을때
            logger.error('Exception:%s', e.output.strip())
            return {'ret': 'no_bin', 'log': e.output.strip()}
        except Exception as e:
            # 그 외의 에러, 대부분 데이터베이스가 없어서 json 값이 들어오지 않는 경우
            logger.error('Exception:%s', e)
            return {'ret': 'no_json', 'log': vnstat_stdout}
