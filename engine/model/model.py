from engine.util.supervised_model import ClassificationModels, RegressionModels

from scipy.stats import skew, boxcox
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

import numpy as np
import pandas as pd
import seaborn as sns

from matplotlib import pyplot as plt
from typing import Dict


MAPPING = {
    'classification': ClassificationModels,
    'regression': RegressionModels
}


def standardize_input_for_training(df: pd.DataFrame):

    # Assumed the most right side is true value
    if 'y' not in [name.lower() for name in df.columns]:
        df['y'] = df[df.columns[-1]]

    return df


def apply_simple_imputer_and_encoding(df: pd.DataFrame, strategy='mean'):

    # create two DataFrames, one for each data type
    df_numeric, df_categorical = [df[df.select_dtypes(i).columns] for i in ['number', 'object']]

    # Apply SimpleImputer to numeric columns
    imp = SimpleImputer(missing_values=np.nan, strategy=strategy)
    df_numeric = pd.DataFrame(imp.fit_transform(df_numeric), columns=df_numeric.columns)

    # Label Encoder for color of wine (Red and White wine)
    label_encoder = LabelEncoder()
    for column in df_categorical.columns:
        df_categorical[column] = label_encoder.fit_transform(df_categorical.type.values)

    df = pd.concat([df_numeric, df_categorical], axis=1)

    return df


def apply_boxcox_transformation(df: pd.DataFrame, threshold=0.7):
    # Do for all
    numerical_features = list(df.select_dtypes('number').columns)
    skewed_features = df[numerical_features].apply(lambda x: skew(x.dropna())).sort_values(ascending=False)

    # compute skewness
    skewness = pd.DataFrame({'skew': skewed_features})

    # Get only highest skewed features
    skewness = skewness[abs(skewness) > threshold]
    skewness = skewness.dropna()

    fitted_lambdas = {}

    for feat in skewness.index:
        df[feat], fitted_lambdas[feat] = boxcox((df[feat] + 1))
    return df, fitted_lambdas


def prepare_input_for_training(df: pd.DataFrame, test_size=0.2):

    df = standardize_input_for_training(df)
    df = apply_simple_imputer_and_encoding(df)
    df = apply_boxcox_transformation(df)[0]

    x = df[[i for i in df.columns if i not in ['y']]]
    y = df['y']

    return train_test_split(x.to_numpy(), y.to_numpy(), test_size=test_size)


def correlation_matrix(df):
    fig, ax = plt.subplots(1, 1, figsize=(20, 8))
    corr = df.corr()
    ax.set_title("Correlation Matrix")
    top_corr_cols = corr.quality.sort_values(ascending=False).keys()
    top_corr = corr.loc[top_corr_cols, top_corr_cols]
    dropSelf = np.zeros_like(top_corr)
    dropSelf[np.triu_indices_from(dropSelf)] = True
    return sns.heatmap(top_corr, cmap=sns.diverging_palette(220, 10, as_cmap=True), annot=True, fmt=".2f", mask=dropSelf, ax=ax)


def choose_best_model(data: Dict, scoring='mean'):
    df = pd.DataFrame(data)
    df = df.sort_values(scoring, ascending=False)
    return df.iloc[0].model_name


class SupervisedModels():
    def __init__(self, input_data, problem_type='classification', evaluation_metric='accuracy'):
        self.input_data = input_data
        self.problem_type = problem_type
        self.models = MAPPING.get(self.problem_type)
        self.evaluation_metric = evaluation_metric

    @property
    def numerical_data(self):
        return self.input_data[self.input_data.select_dtypes('number').columns]

    @property
    def categorical_data(self):
        return self.input_data[self.input_data.select_dtypes('object').columns]

    def model_fitting(self, x_train, x_test, y_train, y_test, model='random_forest'):
        selected_model = self.models[model].func
        selected_model.fit(x_train, y_train)
        predictions = selected_model.predict(x_test)

        score = accuracy_score(y_test, predictions)
        matrix = confusion_matrix(y_test, predictions)
        report = classification_report(y_test, predictions)

        return score, matrix, report

    def run_pipeline(self):
        X_train, X_test, y_train, y_test = prepare_input_for_training(self.input_data)
        models = list(self.models.__members__.keys())
        results_k_fold = []
        for model in models:
            k_fold = StratifiedKFold(n_splits=5)
            cv_results = cross_val_score(self.models[model].func, X_train, y_train, cv=k_fold, scoring='accuracy')
            results_k_fold.append({'model_name': model, 'mean': cv_results.mean(), 'std': cv_results.std()})
        print(results_k_fold)

        # Use the best model to provide analysis to the users.
        best_model = choose_best_model(results_k_fold)
        print(best_model)

        return self.model_fitting(X_train, X_test, y_train, y_test, model=best_model)