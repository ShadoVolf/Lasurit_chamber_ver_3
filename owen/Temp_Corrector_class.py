import numpy as np
import joblib
import pickle
import sklearn
import scipy
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from typing import Union, Tuple, Optional, List



class PolynomialCorrector:
    """
    Класс для калибровки датчика температуры с помощью полиномиальной регрессии.
    Позволяет обучить модель, скорректировать новые значения, сохранить и загрузить.
    """

    def __init__(self):
        self.coefficients = None  # коэффициенты полинома (старшая степень -> младшая)
        self.degree = None  # степень полинома
        self.poly_func = None  # np.poly1d объект для быстрого вычисления

    def fit(self, sensor_data: np.ndarray, real_data: np.ndarray, degree: int) -> 'PolynomialCorrector':
        """
        Обучение полиномиальной модели методом МНК.

        Параметры
        ---------
        sensor_data : array-like
            Показания датчика.
        real_data : array-like
            Реальные значения температуры.
        degree : int
            Степень полинома.

        Возвращает
        ----------
        self
        """
        sensor_data = np.asarray(sensor_data).flatten()
        real_data = np.asarray(real_data).flatten()

        self.coefficients = np.polyfit(sensor_data, real_data, degree)
        self.degree = degree
        self.poly_func = np.poly1d(self.coefficients)
        return self

    def predict(self, x: Union[float, List[float], np.ndarray]) -> np.ndarray:
        """
        Применить коррекцию к одному или нескольким значениям.

        Параметры
        ---------
        x : float или список/массив
            Значения, полученные с датчика.

        Возвращает
        ----------
        numpy.ndarray
            Скорректированные значения температуры.
        """
        if self.poly_func is None:
            raise ValueError("Модель не обучена. Вызовите метод fit() перед predict().")
        x = np.asarray(x, dtype=float)
        return self.poly_func(x)

    def save(self, filepath: str) -> None:
        """
        Сохранить обученную модель в файл (pickle).

        Параметры
        ---------
        filepath : str
            Путь к файлу для сохранения.
        """
        if self.coefficients is None:
            raise ValueError("Модель не обучена. Нечего сохранять.")
        with open(filepath, 'wb') as f:
            pickle.dump({
                'coefficients': self.coefficients,
                'degree': self.degree
            }, f)

    @staticmethod
    def load(filepath: str) -> 'PolynomialCorrector':
        """
        Загрузить модель из файла.

        Параметры
        ---------
        filepath : str
            Путь к файлу.

        Возвращает
        ----------
        PolynomialCorrector
            Загруженный объект-корректор.
        """
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        corrector = PolynomialCorrector()
        corrector.coefficients = data['coefficients']
        corrector.degree = data['degree']
        corrector.poly_func = np.poly1d(corrector.coefficients)
        return corrector


class NeuralCorrector:
    """
    Класс для калибровки датчика температуры с помощью нейронной сети (MLPRegressor).
    Включает стандартизацию данных, обучение, предсказание, сохранение и загрузку.
    """

    def __init__(self):
        self.model = None  # обученный MLPRegressor
        self.scaler_X = None  # StandardScaler для входных признаков
        self.scaler_y = None  # StandardScaler для выходных значений
        self.is_fitted = False

    def fit(
            self,
            sensor_data: np.ndarray,
            real_data: np.ndarray,
            hidden_layer_sizes: Tuple[int, ...] = (10,),
            activation: str = 'relu',
            max_iter: int = 2000,
            random_state: int = 42,
            **kwargs
    ) -> 'NeuralCorrector':
        """
        Обучение нейросетевой модели.

        Параметры
        ---------
        sensor_data : array-like
            Показания датчика.
        real_data : array-like
            Реальные значения температуры.
        hidden_layer_sizes : tuple
            Количество нейронов в скрытых слоях.
        activation : str
            Функция активации ('relu', 'tanh', 'logistic' и др.).
        max_iter : int
            Максимальное количество итераций обучения.
        random_state : int
            Seed для воспроизводимости.
        **kwargs
            Дополнительные параметры для MLPRegressor.

        Возвращает
        ----------
        self
        """
        X = np.asarray(sensor_data).reshape(-1, 1)
        y = np.asarray(real_data).flatten()

        # Стандартизация
        self.scaler_X = StandardScaler()
        X_scaled = self.scaler_X.fit_transform(X)

        self.scaler_y = StandardScaler()
        y_scaled = self.scaler_y.fit_transform(y.reshape(-1, 1)).ravel()

        # Инициализация и обучение модели
        self.model = MLPRegressor(
            hidden_layer_sizes=hidden_layer_sizes,
            activation=activation,
            max_iter=max_iter,
            random_state=random_state,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=50,
            **kwargs
        )
        self.model.fit(X_scaled, y_scaled)
        self.is_fitted = True
        return self

    def predict(self, x: Union[float, List[float], np.ndarray]) -> np.ndarray:
        """
        Применить коррекцию к одному или нескольким значениям.

        Параметры
        ---------
        x : float или список/массив
            Значения, полученные с датчика.

        Возвращает
        ----------
        numpy.ndarray
            Скорректированные значения температуры.
        """
        if not self.is_fitted:
            raise ValueError("Модель не обучена. Вызовите метод fit() перед predict().")
        X = np.asarray(x).reshape(-1, 1)
        X_scaled = self.scaler_X.transform(X)
        y_pred_scaled = self.model.predict(X_scaled)
        y_pred = self.scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).ravel()
        return y_pred

    def save(self, filepath: str) -> None:
        """
        Сохранить обученную модель и стандартизаторы в файл (joblib).

        Параметры
        ---------
        filepath : str
            Путь к файлу для сохранения.
        """
        if not self.is_fitted:
            raise ValueError("Модель не обучена. Нечего сохранять.")
        joblib.dump({
            'model': self.model,
            'scaler_X': self.scaler_X,
            'scaler_y': self.scaler_y
        }, filepath)

    @staticmethod
    def load(filepath: str) -> 'NeuralCorrector':
        """
        Загрузить модель из файла.

        Параметры
        ---------
        filepath : str
            Путь к файлу.

        Возвращает
        ----------
        NeuralCorrector
            Загруженный объект-корректор.
        """
        data = joblib.load(filepath)
        corrector = NeuralCorrector()
        corrector.model = data['model']
        corrector.scaler_X = data['scaler_X']
        corrector.scaler_y = data['scaler_y']
        corrector.is_fitted = True
        return corrector

