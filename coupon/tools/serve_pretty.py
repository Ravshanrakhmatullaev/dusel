# Cloudflare Pages kabi: /coupon -> coupon.html, mavjud bo'lmasa 404.html (faqat lokal test uchun)
import http.server, os, sys
root=sys.argv[1]; port=int(sys.argv[2])
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=root,**k)
    def send_head(s):
        path=s.path.split('?',1)[0]
        fs=os.path.join(root,path.lstrip('/'))
        if path!='/' and not os.path.exists(fs) and os.path.exists(fs+'.html'):
            s.path=path+'.html'+(('?'+s.path.split('?',1)[1]) if '?' in s.path else '')
        elif path!='/' and not os.path.exists(fs):
            s.path='/404.html'
        return super().send_head()
    def log_message(s,*a): pass
http.server.ThreadingHTTPServer(('127.0.0.1',port),H).serve_forever()
