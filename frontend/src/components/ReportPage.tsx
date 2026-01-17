import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

// Интерфейсы для типизации данных отчёта
// Соответствуют моделям из Reports API
interface ReportItem {
  user_id: number;
  prosthesis_id: number;
  report_date: string;
  report_hour: string;
  movements_count: number;
  battery_level_avg: number;
  battery_level_min: number;
  battery_level_max: number;
  usage_hours: number;
  avg_movements_per_hour: number;
  peak_activity_hour: number;
  crm_user_name: string;
  crm_prosthesis_model: string;
  crm_prosthesis_serial: string;
}

interface ReportResponse {
  user_id: number;
  total_records: number;
  date_from: string | null;
  date_to: string | null;
  reports: ReportItem[];
  summary: {
    total_movements: number;
    total_usage_hours: number;
    avg_battery_level: number;
    prostheses_count: number;
    days_covered: number;
    warning?: string;  // Предупреждение о недоступности данных
    info?: string;      // Информационное сообщение
  };
}

const ReportPage: React.FC = () => {
  // Хук для работы с Keycloak (аутентификация)
  const { keycloak, initialized } = useKeycloak();
  
  // Состояния компонента
  const [loading, setLoading] = useState(false); // Индикатор загрузки
  const [error, setError] = useState<string | null>(null); // Сообщение об ошибке
  const [reportData, setReportData] = useState<ReportResponse | null>(null); // Данные отчёта
  const [dateFrom, setDateFrom] = useState<string>(''); // Фильтр: начальная дата
  const [dateTo, setDateTo] = useState<string>(''); // Фильтр: конечная дата

  /**
   * Функция для получения отчёта из Reports API
   * Вызывает эндпоинт /reports с токеном аутентификации
   * RBAC: пользователь автоматически получает только свои отчёты (user_id из токена)
   */
  const fetchReport = async () => {
    // Проверка наличия токена аутентификации
    // Без токена запрос к API будет отклонён с ошибкой 401
    if (!keycloak?.token) {
      setError('Необходима аутентификация. Пожалуйста, войдите в систему.');
      return;
    }

    try {
      // Установка состояния загрузки и очистка предыдущих ошибок
      setLoading(true);
      setError(null);
      setReportData(null);

      // Формирование URL для запроса к Reports API
      // REACT_APP_API_URL указывает на адрес Reports API (http://localhost:8000)
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      let url = `${apiUrl}/reports`;

      // Добавление параметров фильтрации по датам, если они указаны
      // Эти параметры опциональны - если не указаны, API вернёт данные за последние 30 дней
      const params = new URLSearchParams();
      if (dateFrom) {
        params.append('date_from', dateFrom);
      }
      if (dateTo) {
        params.append('date_to', dateTo);
      }
      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      // Выполнение HTTP GET запроса к Reports API
      // Authorization header содержит токен Keycloak для аутентификации
      // Reports API извлечёт user_id из токена и вернёт только данные этого пользователя
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${keycloak.token}`, // Токен для аутентификации
          'Content-Type': 'application/json'
        }
      });

      // Проверка статуса ответа
      // 401 - неавторизован (токен невалиден или отсутствует)
      // 500 - ошибка сервера
      // 200 - успешный запрос
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Ошибка аутентификации. Пожалуйста, войдите в систему снова.');
        } else if (response.status === 500) {
          throw new Error('Ошибка сервера при получении отчёта. Попробуйте позже.');
        } else {
          throw new Error(`Ошибка при получении отчёта: ${response.statusText}`);
        }
      }

      // Парсинг JSON ответа от API
      // Ответ содержит массив отчётов и сводную статистику
      const data: ReportResponse = await response.json();
      
      // Сохранение данных отчёта в состояние компонента
      setReportData(data);
      
      console.log(`Получен отчёт для пользователя ${data.user_id}, записей: ${data.total_records}`);
      
    } catch (err) {
      // Обработка ошибок: сетевые ошибки, ошибки парсинга, ошибки API
      const errorMessage = err instanceof Error ? err.message : 'Произошла неизвестная ошибка';
      setError(errorMessage);
      console.error('Ошибка при получении отчёта:', err);
    } finally {
      // Сброс состояния загрузки в любом случае (успех или ошибка)
      setLoading(false);
    }
  };

  /**
   * Функция для скачивания отчёта в формате JSON
   * Создаёт файл с данными отчёта и инициирует его скачивание
   */
  const downloadReportAsJSON = () => {
    if (!reportData) {
      setError('Нет данных для скачивания. Сначала получите отчёт.');
      return;
    }

    try {
      // Преобразование данных отчёта в JSON строку с форматированием
      const jsonData = JSON.stringify(reportData, null, 2);
      
      // Создание Blob объекта с типом application/json
      // Blob позволяет создать файл в памяти браузера
      const blob = new Blob([jsonData], { type: 'application/json' });
      
      // Создание URL для Blob объекта
      const url = URL.createObjectURL(blob);
      
      // Создание временного элемента <a> для скачивания файла
      const link = document.createElement('a');
      link.href = url;
      
      // Формирование имени файла с датой и временем
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      link.download = `prosthesis-report-${timestamp}.json`;
      
      // Добавление ссылки в DOM, клик по ней и удаление
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // Освобождение памяти, занятой Blob URL
      URL.revokeObjectURL(url);
      
      console.log('Отчёт скачан в формате JSON');
    } catch (err) {
      setError('Ошибка при скачивании отчёта');
      console.error('Ошибка скачивания:', err);
    }
  };

  /**
   * Функция для скачивания отчёта в формате CSV
   * Преобразует данные отчёта в CSV формат и инициирует скачивание
   */
  const downloadReportAsCSV = () => {
    if (!reportData || !reportData.reports.length) {
      setError('Нет данных для скачивания. Сначала получите отчёт.');
      return;
    }

    try {
      // Заголовки CSV файла
      const headers = [
        'Дата',
        'Время',
        'ID протеза',
        'Количество движений',
        'Уровень батареи (средний)',
        'Уровень батареи (мин)',
        'Уровень батареи (макс)',
        'Часы использования',
        'Движений в час (среднее)',
        'Пиковый час активности',
        'Модель протеза',
        'Серийный номер'
      ];

      // Преобразование данных отчёта в строки CSV
      // Каждая строка содержит данные одного записи отчёта
      const csvRows = [
        headers.join(','), // Первая строка - заголовки
        ...reportData.reports.map(report => [
          report.report_date,
          report.report_hour,
          report.prosthesis_id,
          report.movements_count,
          report.battery_level_avg.toFixed(2),
          report.battery_level_min.toFixed(2),
          report.battery_level_max.toFixed(2),
          report.usage_hours.toFixed(2),
          report.avg_movements_per_hour.toFixed(2),
          report.peak_activity_hour,
          `"${report.crm_prosthesis_model}"`, // Кавычки для строк с пробелами
          `"${report.crm_prosthesis_serial}"`
        ].join(','))
      ];

      // Объединение всех строк в одну CSV строку
      const csvContent = csvRows.join('\n');
      
      // Создание Blob объекта с типом text/csv
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      
      // Создание ссылки для скачивания
      const link = document.createElement('a');
      link.href = url;
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      link.download = `prosthesis-report-${timestamp}.csv`;
      
      // Инициация скачивания
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
      console.log('Отчёт скачан в формате CSV');
    } catch (err) {
      setError('Ошибка при скачивании отчёта в формате CSV');
      console.error('Ошибка скачивания CSV:', err);
    }
  };

  // Отображение индикатора загрузки, пока Keycloak инициализируется
  if (!initialized) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="text-lg">Загрузка...</div>
      </div>
    );
  }

  // Отображение страницы входа, если пользователь не аутентифицирован
  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">Отчёты о работе протеза</h1>
          <p className="mb-4 text-gray-600">Для просмотра отчётов необходимо войти в систему</p>
          <button
            onClick={() => keycloak.login()}
            className="px-6 py-3 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
          >
            Войти
          </button>
        </div>
      </div>
    );
  }

  // Основной интерфейс для аутентифицированных пользователей
  return (
    <div className="flex flex-col items-center min-h-screen bg-gray-100 py-8">
      <div className="w-full max-w-6xl p-8 bg-white rounded-lg shadow-md">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">Отчёты о работе протеза</h1>
          <button
            onClick={() => keycloak.logout()}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          >
            Выйти
          </button>
        </div>

        {/* Фильтры по датам */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h2 className="text-lg font-semibold mb-4">Фильтры</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Дата начала (необязательно)
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                max={new Date(Date.now() - 86400000).toISOString().split('T')[0]} // Максимум - вчера
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Дата окончания (необязательно)
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                max={new Date(Date.now() - 86400000).toISOString().split('T')[0]} // Максимум - вчера
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded">
            <p className="text-sm text-yellow-800">
              <strong>Важно:</strong> Данные обрабатываются ежедневно в 02:00 UTC. 
              Данные за сегодня могут быть ещё не доступны. 
              Рекомендуется запрашивать данные до вчерашнего дня включительно.
            </p>
          </div>
          <p className="mt-2 text-sm text-gray-500">
            Если даты не указаны, будут показаны данные за последние 30 дней (до вчерашнего дня)
          </p>
        </div>

        {/* Кнопка получения отчёта */}
        <div className="mb-6">
          <button
            onClick={fetchReport}
            disabled={loading}
            className={`px-6 py-3 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Загрузка отчёта...' : 'Получить отчёт'}
          </button>
        </div>

        {/* Отображение ошибок */}
        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            <strong>Ошибка:</strong> {error}
          </div>
        )}

        {/* Отображение данных отчёта */}
        {reportData && (
          <div className="space-y-6">
            {/* Предупреждения и информационные сообщения */}
            {reportData.summary.warning && (
              <div className="p-4 bg-yellow-100 border border-yellow-400 text-yellow-800 rounded">
                <strong>Предупреждение:</strong> {reportData.summary.warning}
              </div>
            )}
            {reportData.summary.info && (
              <div className="p-4 bg-blue-100 border border-blue-400 text-blue-800 rounded">
                <strong>Информация:</strong> {reportData.summary.info}
              </div>
            )}
            
            {/* Сводная статистика */}
            <div className="p-6 bg-blue-50 rounded-lg">
              <h2 className="text-xl font-semibold mb-4">Сводная статистика</h2>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div>
                  <div className="text-sm text-gray-600">Всего движений</div>
                  <div className="text-2xl font-bold">{reportData.summary.total_movements}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Часов использования</div>
                  <div className="text-2xl font-bold">{reportData.summary.total_usage_hours.toFixed(1)}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Средний уровень батареи</div>
                  <div className="text-2xl font-bold">{reportData.summary.avg_battery_level.toFixed(1)}%</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Количество протезов</div>
                  <div className="text-2xl font-bold">{reportData.summary.prostheses_count}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Дней в отчёте</div>
                  <div className="text-2xl font-bold">{reportData.summary.days_covered}</div>
                </div>
              </div>
            </div>

            {/* Кнопки скачивания */}
            <div className="flex gap-4">
              <button
                onClick={downloadReportAsJSON}
                className="px-6 py-3 bg-green-500 text-white rounded hover:bg-green-600 transition-colors"
              >
                Скачать JSON
              </button>
              <button
                onClick={downloadReportAsCSV}
                className="px-6 py-3 bg-green-500 text-white rounded hover:bg-green-600 transition-colors"
              >
                Скачать CSV
              </button>
            </div>

            {/* Таблица с данными отчёта */}
            <div className="overflow-x-auto">
              <h2 className="text-xl font-semibold mb-4">
                Детальные данные ({reportData.total_records} записей)
              </h2>
              <table className="min-w-full bg-white border border-gray-300">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-4 py-2 border-b text-left">Дата</th>
                    <th className="px-4 py-2 border-b text-left">Время</th>
                    <th className="px-4 py-2 border-b text-left">ID протеза</th>
                    <th className="px-4 py-2 border-b text-right">Движения</th>
                    <th className="px-4 py-2 border-b text-right">Батарея (ср.)</th>
                    <th className="px-4 py-2 border-b text-right">Часы</th>
                    <th className="px-4 py-2 border-b text-left">Модель</th>
                  </tr>
                </thead>
                <tbody>
                  {reportData.reports.slice(0, 50).map((report, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-2 border-b">{report.report_date}</td>
                      <td className="px-4 py-2 border-b">{new Date(report.report_hour).toLocaleTimeString()}</td>
                      <td className="px-4 py-2 border-b">{report.prosthesis_id}</td>
                      <td className="px-4 py-2 border-b text-right">{report.movements_count}</td>
                      <td className="px-4 py-2 border-b text-right">{report.battery_level_avg.toFixed(1)}%</td>
                      <td className="px-4 py-2 border-b text-right">{report.usage_hours.toFixed(2)}</td>
                      <td className="px-4 py-2 border-b">{report.crm_prosthesis_model || 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {reportData.reports.length > 50 && (
                <p className="mt-2 text-sm text-gray-500">
                  Показано 50 из {reportData.reports.length} записей. Скачайте полный отчёт для просмотра всех данных.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
