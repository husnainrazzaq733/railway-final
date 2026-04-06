import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

try:
    from cpanel_app import app as application
except Exception as e:
    import traceback
    error_html = "<html><body><h1>cPanel App Error</h1><pre>" + traceback.format_exc() + "</pre></body></html>"
    
    # A tiny fake WSGI app to display the error in the browser
    def application(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/html')]
        start_response(status, headers)
        return [error_html.encode('utf-8')]
