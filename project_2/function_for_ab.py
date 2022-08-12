import pandas as pd
import numpy as np
import requests
from urllib.parse import urlencode
import json
import matplotlib.pyplot as plt
import plotly
import plotly.graph_objs as go


'''
На вход функции подается: 
group_df - датафрейм со старыми данными,
active_studs_df - датафрейм с активными в дни проведения эксперимента пользователями,
checks_df - датафрейм с оплатами
link_to_file - ссылка до новых данных,
sep_in_file - разделитель в файле

Функция возвращает:
1) Обновленный датафрейм group_df,
2) Пересчитанную таблицу с метриками CR и AOV
'''
def add_data_to_groups(groups_df, active_studs_df, checks_df,  link_to_file='default', sep_in_file=','):
    if link_to_file == 'default':
        base_url = 'https://cloud-api.yandex.net/v1/disk/public/resources/download?'
        public_key = 'https://disk.yandex.ru/d/3aARY-P9pfaksg'  # Ссылка на яндекс диск

        # Получаем загрузочную ссылку
        final_url = base_url + urlencode(dict(public_key=public_key))
        response = requests.get(final_url)
        download_url = response.json()['href']
    else:
        download_url = link_to_file
    # Получаем dataframe
    groups_add_df = pd.read_csv(download_url, sep=sep_in_file)
    
    # Удаляем строки с пропусками
    groups_add_df.dropna(inplace=True)
    
    # Удаляем дубликаты
    groups_add_df.drop_duplicates(inplace=True)
    
    # Добавим новые данные в таблицу groups_df
    groups_df = pd.DataFrame(np.concatenate((groups_df.values, groups_add_df.values), axis=0))
    groups_df.columns = ['id', 'grp']
    
    # Нас интересуют пользователи, которые заходили на платформу 
    active_studs_groups_df = groups_df.query('id in @active_studs_df.student_id').rename(columns={'id' : 'student_id'})
    
    # Добавим данные по оплате. Если не оплачивал, ставим 0.
    ab_df = active_studs_groups_df.merge(checks_df, how='left', on='student_id').fillna(0)
    
    # Добавим колонку с платежной информацией(если покупал True, иначе False)
    ab_df['isPay'] = (ab_df.rev > 0)
    
    # Считаем метрики
    metric = ab_df.groupby('grp', as_index=0).agg({'isPay' : 'mean', 'rev' : 'mean'}). \
    rename(columns={'isPay': 'CR', 'rev' : 'AOV'})
    #Выводим
    return groups_df, metric


'''
На вход функции подается: 
all_result - список из датафреймов метрик,
name_metric - название метрики

Функция строит график по определенной метрике, где по х(условно, сколько дней прошло с начала эксперимента), по y - значение метрики.
'''
def print_metric(all_result, name_metric='CR'):
    A_data = [i[name_metric][0] for i in all_result]
    B_data = [i[name_metric][1] for i in all_result]
    # Строим график
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[i+1 for  i in range(len(all_result))], y=A_data, mode='lines+markers', name='Группа A'))
    fig.add_trace(go.Scatter(x=[i+1 for  i in range(len(all_result))], y=B_data, mode='lines+markers', name='Группа B'))
    fig.update_layout(legend_orientation="h",
                      legend=dict(x=.5, xanchor="center"),
                      title=f'{name_metric}',
                      xaxis_title="Прошло дней с эксперимента",
                      yaxis_title="Значение метрики",
                      margin=dict(l=0, r=0, t=30, b=0))
    fig.show()