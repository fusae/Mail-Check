"""
将以下代码添加到 api_server.py 中
位置：在 if __name__ == '__main__': 之前
"""

# ========== 添加以下代码到 api_server.py ==========

@app.route('/api/report/generate', methods=['POST'])
def api_generate_report():
    """
    生成舆情报告API

    请求参数（JSON）：
    {
        "start_date": "2026-01-01",  // 可选
        "end_date": "2026-01-31",    // 可选
        "hospital": "医院名称",       // 可选
        "period": "2026年第一季度",   // 可选
        "format": "markdown"         // markdown/word/both
    }

    返回：
    {
        "success": true,
        "files": {
            "markdown": "/path/to/report.md",
            "word": "/path/to/report.docx"
        },
        "summary": {...}
    }
    """
    try:
        data = request.get_json() or {}

        start_date = data.get('start_date')
        end_date = data.get('end_date')
        hospital = data.get('hospital')
        period = data.get('period')
        output_format = data.get('format', 'markdown')

        # 导入报告生成器
        from report_generator_mailcheck import MailCheckReportGenerator

        # 生成报告
        generator = MailCheckReportGenerator(db_path=DB_PATH)
        result = generator.generate_report(
            start_date=start_date,
            end_date=end_date,
            hospital=hospital,
            report_period=period,
            output_format=output_format
        )

        if result['success']:
            # 返回文件路径（相对路径）
            files = {}
            for fmt, path in result.get('files', {}).items():
                # 转换为相对路径
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
            return jsonify({
                'success': False,
                'message': result.get('message', '生成失败')
            }), 500

    except Exception as e:
        logging.exception("Failed to generate report")
        return jsonify({
            'success': False,
            'message': f'生成报告失败: {str(e)}'
        }), 500


@app.route('/api/report/download/<filename>', methods=['GET'])
def api_download_report(filename):
    """
    下载生成的报告

    参数：
    - filename: 报告文件名（如 "XX医院_舆情报告_20260131_120000.md"）
    """
    try:
        # 安全检查文件名
        if not filename or '..' in filename or '/' in filename:
            return jsonify({'success': False, 'message': '无效的文件名'}), 400

        # 查找文件
        reports_dir = os.path.join(os.path.dirname(DB_PATH), 'reports')
        file_path = os.path.join(reports_dir, filename)

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '文件不存在'}), 404

        # 返回文件
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logging.exception("Failed to download report")
        return jsonify({
            'success': False,
            'message': f'下载失败: {str(e)}'
        }), 500


@app.route('/api/report/list', methods=['GET'])
def api_list_reports():
    """
    列出已生成的报告

    返回：
    {
        "success": true,
        "reports": [
            {
                "filename": "XX医院_舆情报告_20260131.md",
                "created_at": "2026-01-31 12:00:00",
                "size": 12345,
                "format": "markdown"
            }
        ]
    }
    """
    try:
        reports_dir = os.path.join(os.path.dirname(DB_PATH), 'reports')

        if not os.path.exists(reports_dir):
            return jsonify({'success': True, 'reports': []})

        reports = []
        for filename in os.listdir(reports_dir):
            file_path = os.path.join(reports_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                file_ext = os.path.splitext(filename)[1].lower()
                fmt = 'word' if file_ext == '.docx' else 'markdown'

                reports.append({
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': stat.st_size,
                    'format': fmt
                })

        # 按创建时间倒序
        reports.sort(key=lambda x: x['created_at'], reverse=True)

        return jsonify({
            'success': True,
            'reports': reports[:50]  # 只返回最近50个
        })

    except Exception as e:
        logging.exception("Failed to list reports")
        return jsonify({
            'success': False,
            'message': f'获取列表失败: {str(e)}'
        }), 500

# ========== 添加代码结束 ==========
