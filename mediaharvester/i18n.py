"""Static UI translation catalog. Technical engine diagnostics retain their original language."""
EN={
 '首页':'Home','URL 解析':'Analyze URLs','视频下载':'Videos','图片下载':'Images','下载任务':'Downloads','已完成':'Completed','下载历史':'History','设置':'Settings',
 '未知':'Unknown','等待 URL':'Enter URLs to begin','开始解析 URL':'Analyze URLs',
 '解析网页中的视频、音频和图片':'Find videos, audio and images on a web page',
 '输入网页地址，选择真实媒体格式，然后下载。\n任务、进度和临时文件会自动保存。':'Enter a page URL, select an available format, and download.\nTasks, progress and partial files are saved automatically.',
 '粘贴':'Paste','解析 / 重新解析':'Analyze / Refresh','清空':'Clear','取消解析':'Cancel analysis','深度解析（动态网页）':'Deep analysis (dynamic pages)',
 '隐藏重复 URL':'Hide duplicate URLs','全选':'Select all','取消全选':'Clear selection','按分辨率排序':'Sort by resolution','下载选中媒体':'Download selected',
 '暂停':'Pause','继续 / 重试':'Resume / Retry','取消':'Cancel','删除记录':'Delete records','打开文件':'Open file','打开文件夹':'Open folder',
 '前往解析':'Go to analysis','视频格式在 URL 解析页选择；这里显示视频下载任务。':'Choose video formats on the analysis page. Video tasks appear here.',
 '图片可在 URL 解析页筛选并批量选择。':'Filter and select images on the analysis page.',
 '已完成文件':'Completed files','完整任务历史（包含失败与取消）':'Task history (including failures and cancellations)',
 '下载文件夹':'Download folder','最大并发任务':'Concurrent tasks','单任务连接数':'Connections per task','每任务限速 B/s（0 不限）':'Rate limit per task, B/s (0 unlimited)',
 '重试次数':'Retry count','退避初始秒数':'Initial retry delay (seconds)','单页最大图片数':'Maximum images per page','启动自动恢复':'Resume on startup',
 '完成通知':'Completion notifications','图片内容 SHA-256 去重':'Deduplicate images using SHA-256','下载字幕':'Download subtitles','保存视频封面':'Save video thumbnail',
 '优先 MP4':'Prefer MP4','自动合并音视频':'Merge video and audio','优先页面明确原图':'Prefer largest explicit image candidate',
 '默认图片最小宽度':'Default minimum image width','默认图片最小高度':'Default minimum image height','选择下载文件夹':'Choose download folder',
 '主题':'Theme','语言':'Language','默认画质':'Default quality','合并输出容器（编码不兼容时使用 MKV）':'Merge container (MKV if codecs are incompatible)',
 '命名方式':'Filename style','保存设置':'Save settings',
 '语言结构已预留；当前正文以简体中文为主。':'UI translations available; some engine messages use Chinese.',
 '格式过滤，如 jpg':'Filter extension, e.g. jpg',
 '自定义文件名（仅选择单项时应用，默认保留原标题）':'Custom filename (one selected item only; original title by default)',
 'https://example.com/video\n每行一个 HTTP/HTTPS 地址':'https://example.com/video\nOne HTTP/HTTPS URL per line',
 '选择 / 预览':'Select / Preview','类型':'Type','标题 / 来源':'Title / Source','尺寸 / 时长':'Dimensions / Duration','格式 / 大小':'Format / Size',
 '画质 / 格式选择':'Quality / Format','音频输出':'Audio output','原始地址':'Source URL',
 '文件':'File','类型 / 引擎':'Type / Engine','状态':'Status','进度':'Progress','已下载 / 总量':'Downloaded / Total','速度':'Speed','剩余时间':'ETA','错误信息':'Error',
}

def translate(text,language):
    return EN.get(text,text) if language=='en_US' else text

def localize(root,language):
    from PySide6.QtWidgets import QLabel,QAbstractButton,QLineEdit,QPlainTextEdit
    for widget in root.findChildren(QLabel)+root.findChildren(QAbstractButton):
        original=widget.property('mh_original_text')
        if original is None:
            original=widget.text(); widget.setProperty('mh_original_text',original)
        widget.setText(translate(original,language))
    for widget in root.findChildren(QLineEdit)+root.findChildren(QPlainTextEdit):
        original=widget.property('mh_original_placeholder')
        if original is None:
            original=widget.placeholderText(); widget.setProperty('mh_original_placeholder',original)
        widget.setPlaceholderText(translate(original,language))
