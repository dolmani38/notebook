import inspect
import os
import sys

import pandas as pd

def csvlist(path="."):
    """
    csv 파일의 list를 표출한다.
    선택한 파일은 DataFrame형식으로 python runtime에 load된다.
    :param path: csv파일이 저장되어 있는 폴더 위치
    :return: DataFrame
    """
    ls = []
    for s in os.listdir(path):
        if s.endswith(".csv"):
            ls.append("<a href=\"javascript:ctrl_file('__load_csv','" + path +"/" + s + "')\">" + s + "</a>")
    print('\n'.join(ls))

def __load_csv(path):
    """
    해당 path의 csv 파일을 load한다.
    :param path: csv 파일 path
    :return:
    """
    df = pd.read_csv(path)
    return df

def structure(df):
    """
    DataFrame의 column 등 전반적인 구조를 표출 한다.
    :param df:
    :return:
    """
    df1 = df.describe(include='all').T
    df1['type'] = df.dtypes
    df1['null count'] = df.isnull().sum()
    if 'freq' in df1.columns:
        df2 = df1[
            ['type', 'count', 'null count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max', 'unique', 'top',
             'freq']]
    else:
        df2 = df1[['type', 'count', 'null count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']]

    return df2

def builtin():
    functions = inspect.getmembers(sys.modules[__name__], inspect.isfunction)
    for fnc in functions:
        print("Builtin method:", fnc[0])
        print("Description:", fnc[1].__doc__)
        print("")