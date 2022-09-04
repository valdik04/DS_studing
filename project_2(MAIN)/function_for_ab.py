import pandas as pd
import numpy as np
import requests
from urllib.parse import urlencode
import json
import pingouin as pg
import matplotlib.pyplot as plt
import plotly
import plotly.graph_objs as go
from scipy.stats import norm


def get_bootstrap(
    data_column_1, # числовые значения первой выборки
    data_column_2, # числовые значения второй выборки
    boot_it = 1000, # количество бутстрап-подвыборок
    statistic = np.mean, # интересующая нас статистика
    bootstrap_conf_level = 0.95 # уровень значимости
):
    boot_data = []
    for i in range(boot_it): # извлекаем подвыборки
        samples_1 = data_column_1.sample(
            len(data_column_1), 
            replace = True # параметр возвращения
        ).values
        
        samples_2 = data_column_2.sample(
            len(data_column_1), 
            replace = True
        ).values
        
        boot_data.append(statistic(samples_1)-statistic(samples_2)) # mean() - применяем статистику
        
    pd_boot_data = pd.DataFrame(boot_data)
        
    left_quant = (1 - bootstrap_conf_level)/2
    right_quant = 1 - (1 - bootstrap_conf_level) / 2
    quants = pd_boot_data.quantile([left_quant, right_quant])
        
    p_1 = norm.cdf(
        x = 0, 
        loc = np.mean(boot_data), 
        scale = np.std(boot_data)
    )
    p_2 = norm.cdf(
        x = 0, 
        loc = -np.mean(boot_data), 
        scale = np.std(boot_data)
    )
    p_value = min(p_1, p_2) * 2
       
    return {"boot_data": boot_data, 
            "quants": quants, 
            "p_value": p_value}



'''
На вход функции подается: 
group_df - датафрейм со старыми данными,
active_studs_df - датафрейм с активными в дни проведения эксперимента пользователями,
checks_df - датафрейм с оплатами
link_to_file - ссылка до новых данных,
sep_in_file - разделитель в файле

Функция возвращает:
1) p-value для CR посчитанную с помощью хи-квадрат
2) p_value для APRU и ARPAU
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
    
    if groups_df.id.nunique() != groups_df.id.count():
        print('New data have old users')
    
    # Нас интересуют пользователи, которые заходили на платформу 
    active_studs_groups_df = groups_df.query('id in @active_studs_df.student_id').rename(columns={'id' : 'student_id'})
    
    # Добавим данные по оплате. Если не оплачивал, ставим 0.
    ab_df = active_studs_groups_df.merge(checks_df, how='left', on='student_id').fillna(0)
    
    # Добавим колонку с платежной информацией(если покупал True, иначе False)
    ab_df['isPay'] = (ab_df.rev > 0)
    
    # Считаем метрики
    metric_df = ab_df.groupby('grp', as_index=0).agg({'isPay' : ['mean', 'sum'], 'rev' : ['mean', 'sum']}). \
    rename(columns={'isPay': 'CR', 'rev' : 'ARPU'})
    metric_df.columns = ['grp', 'CR','sum_users','ARPU', 'sum_rev']
    metric_df['ARPAU'] = metric_df.sum_rev/metric_df.sum_users
    metric_df = metric_df.drop(['sum_users', 'sum_rev'], axis=1)
    
    #Расчитаваем p-value для CR с помощью хи-квадрат
    _, _, p_val_CR = pg.chi2_independence(ab_df, x = 'grp', y = 'isPay')
    
    #Расчитаваем p-value для ARPU  с помощью бутстрап
    result_ARPU = get_bootstrap(data_column_1=ab_df.query('grp == "A"').rev,
    data_column_2=ab_df.query('grp == "B"').rev,
    boot_it = 1000,
    statistic = np.mean,
    bootstrap_conf_level = 0.95)
    
    p_val_ARPU  = result_ARPU['p_value']
    
    #Расчитаваем p-value для ARPAU с помощью бутстрап
    result_ARPAU = get_bootstrap(
    ab_df.query('rev > 0 and grp == "A"').rev, # числовые значения первой выборки
    ab_df.query('rev > 0 and grp == "B"').rev, # числовые значения второй выборки
    boot_it = 1000, # количество бутстрап-подвыборок
    statistic = np.mean, # интересующая нас статистика
    bootstrap_conf_level = 0.95 # уровень значимости
    )
    
    p_val_ARPAU  = result_ARPAU['p_value']
    
    p_value_p_val_ARPU_ARPAU = pd.DataFrame({'p_val_ARPU': [p_val_ARPU], 'p_val_ARPAU': [p_val_ARPAU]})
    
    #Выводим
    return p_val_CR, p_value_p_val_ARPU_ARPAU, groups_df, metric_df
    #return groups_df, metric


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
    
    
