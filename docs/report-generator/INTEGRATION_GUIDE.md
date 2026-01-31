# Mail-Check 舆情报告生成功能集成指南

## ✅ 已完成的集成

### 新增文件

```
Mail-Check/src/
├── report_generator.py              # 核心报告生成引擎（已复制）
├── report_generator_mailcheck.py    # Mail-Check专用包装器
└── api_server.py                    # 需要添加新的API端点
```

### 安装新依赖

```bash
cd C:\Users\Administrator\clawd\Mail-Check

# 添加到requirements.txt：
pandas numpy jinja2 python-docx openpyxl

# 或者直接安装：
pip install pandas numpy jinja2 python-docx openpyxl
```

---

## 🔧 集成步骤

### 步骤1：添加API端点到 api_server.py

打开 `src/api_server.py`，在文件末尾、`if __name__ == '__main__':` 之前添加以下代码：

```python
# ========== 舆情报告生成API ==========

@app.route('/api/report/generate', methods=['POST'])
def api_generate_report():
    """生成舆情报告"""
    try:
        data = request.get_json() or {}

        from report_generator_mailcheck import MailCheckReportGenerator

        generator = MailCheckReportGenerator(db_path=DB_PATH)
        result = generator.generate_report(
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            hospital=data.get('hospital'),
            report_period=data.get('period'),
            output_format=data.get('format', 'markdown')
        )

        if result['success']:
            files = {}
            for fmt, path in result.get('files', {}).items():
                rel_path = os.path.relpath(path, project_root)
                files[fmt] = f"/api/report/download/{os.path.basename(path)}"

            return jsonify({
                'success': True,
                'message': '报告生成成功',
                'files': files,
                'summary': {
                    'hospital': result.get('hospital_name'),
                    'period': result.get('period'),
                    'total_events': result.get('total_events'),
                    'high_risk_events': result.get('high_risk_events')
                }
            })
        else:
            return jsonify({'success': False, 'message': result.get('message')}), 500

    except Exception as e:
        logging.exception("Failed to generate report")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/report/download/<filename>', methods=['GET'])
def api_download_report(filename):
    """下载生成的报告"""
    try:
        reports_dir = os.path.join(os.path.dirname(DB_PATH), 'reports')
        file_path = os.path.join(reports_dir, filename)

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '文件不存在'}), 404

        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        logging.exception("Failed to download report")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/report/list', methods=['GET'])
def api_list_reports():
    """列出已生成的报告"""
    try:
        reports_dir = os.path.join(os.path.dirname(DB_PATH), 'reports')

        if not os.path.exists(reports_dir):
            return jsonify({'success': True, 'reports': []})

        reports = []
        for filename in os.listdir(reports_dir):
            file_path = os.path.join(reports_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                reports.append({
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': stat.st_size
                })

        reports.sort(key=lambda x: x['created_at'], reverse=True)
        return jsonify({'success': True, 'reports': reports[:50]})

    except Exception as e:
        logging.exception("Failed to list reports")
        return jsonify({'success': False, 'message': str(e)}), 500
```

---

## 🚀 使用方法

### 方法1：命令行生成报告

```bash
# 进入项目目录
cd C:\Users\Administrator\clawd\Mail-Check

# 生成本月所有医院的报告
python src/report_generator_mailcheck.py

# 生成指定日期范围
python src/report_generator_mailcheck.py --start-date 2026-01-01 --end-date 2026-01-31

# 生成指定医院的报告
python src/report_generator_mailcheck.py --hospital "XX市第一人民医院"

# 生成Word格式
python src/report_generator_mailcheck.py --format word

# 查看帮助
python src/report_generator_mailcheck.py --help
```

### 方法2：API调用生成报告

```bash
# 启动API服务
python src/api_server.py

# 调用API生成报告
curl -X POST "http://localhost:5003/api/report/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "format": "markdown"
  }'

# 返回：
{
  "success": true,
  "message": "报告生成成功",
  "files": {
    "markdown": "/api/report/download/XX医院_舆情报告_20260131_120000.md"
  },
  "summary": {
    "hospital": "多医院汇总",
    "period": "2026-01-01 至 2026-01-31",
    "total_events": 15,
    "high_risk_events": 10
  }
}

# 下载报告
curl "http://localhost:5003/api/report/download/XX医院_舆情报告_20260131_120000.md" -o report.md

# 查看已生成的报告列表
curl "http://localhost:5003/api/report/list"
```

---

## 📊 生成的报告位置

报告保存在：
```
Mail-Check/data/reports/
├── XX医院_舆情报告_20260131_120000.md
├── XX医院_舆情报告_20260131_120000.docx
└── ...
```

---

## 🎯 报告内容

生成的报告包含：

1. **报告概述** - 总体态势、关键数据
2. **舆情分布** - 时间/平台/类型/科室
3. **重点事件** - Top 5详细分析
4. **情感分析** - 情绪分布 + 关键词
5. **风险评估** - 风险等级 + 影响预测
6. **应对措施** - 立即/短期/长期建议
7. **监测重点** - 平台 + 关键词
8. **附录数据** - 完整事件清单

**约9000字详细分析！**

---

## 💡 示例场景

### 场景1：生成月度报告

```bash
python src/report_generator_mailcheck.py \
  --start-date 2026-01-01 \
  --end-date 2026-01-31 \
  --period "2026年1月" \
  --format both
```

### 场景2：生成特定医院报告

```bash
python src/report_generator_mailcheck.py \
  --hospital "XX市第一人民医院" \
  --period "2026年第一季度"
```

### 场景3：通过API批量生成

```python
import requests

# 生成各医院的报告
hospitals = ["XX市第一人民医院", "XX市第二人民医院"]

for hospital in hospitals:
    response = requests.post(
        "http://localhost:5003/api/report/generate",
        json={
            "hospital": hospital,
            "format": "word"
        }
    )
    print(f"{hospital}: {response.json()}")
```

---

## ✅ 测试验证

```bash
# 测试命令行工具
cd C:\Users\Administrator\clawd\Mail-Check
python src/report_generator_mailcheck.py --start-date 2026-01-01 --end-date 2026-01-31

# 查看生成的报告
ls -lh data/reports/

# 测试API
python src/api_server.py
# 然后在另一个终端：
curl -X POST "http://localhost:5003/api/report/generate" -H "Content-Type: application/json" -d '{}'
```

---

## 📝 注意事项

1. **数据库路径** - 自动从config.yaml读取
2. **报告目录** - 自动创建在data/reports/
3. **依赖安装** - 需要安装pandas、python-docx等
4. **API集成** - 需要手动添加到api_server.py

---

## 🎉 完成！

现在你的Mail-Check系统已经具备完整的舆情报告生成功能！

**下一步：**
1. 安装依赖：`pip install pandas numpy jinja2 python-docx openpyxl`
2. 添加API端点到api_server.py（参考上面的代码）
3. 运行测试：`python src/report_generator_mailcheck.py`

**祝你使用愉快！** 🚀
