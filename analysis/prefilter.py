"""Stage 5, step A: cheap high-recall keyword gate. Candidate = protest term in title or first 1500 chars.
The model decides relevance in step B; this only drops articles that cannot be about a protest."""
import json, glob, os, sys
PROTEST = ["tear gas","unjuk rasa","gen z","sit-in"] + """protest demonstr manifestaz manifestant manifestation corteo cortei sciopero scioperi riot scontri blocus bloqueo
marcha huelga grève streik protesta mobilizzaz occupazion walkout picket barricad unrest uprising lacrimogen lacrymog fumogen mielenosz tüntet demonšt prosvjed
протест демонстр митинг забастов страйк акці мітинг 抗议 示威 游行 罢课 罢工 抗議 デモ 시위 احتجاج مظاهر تظاهر اعتصام إضراب διαδήλ διαμαρτυρ απεργ מחאה הפגנ
प्रदर्शन विरोध आंदोलन বিক্ষোভ ประท้วง biểu tình tüntetés nepokoj neredi nemiri protestoj mótmæl""".split()
YOUTH = """student studen giovan youth young teen school scuol liceo lycée lycéen lycee étudiant universit univers colegio estudiant jóvenes jovenes
schüler schueler jugend jung uczni młodz studen mladi mladež школ студ молод учн 学生 青年 年轻 学校 大学 学生 청년 학생 若者 生徒 طلاب طلبة شباب جامعة
φοιτητ μαθητ νέοι νεολαί סטודנט תלמיד נוער ছাত্র युवा विद्यार्थी นักศึกษา sinh viên kids pupils""".split()
def has(s, terms): return any(t in s for t in terms)
out = open(os.environ.get('OUT','data/relevance_candidates.tsv'),'w'); out.write('outlet\turl\tdate\tprotest_term\tyouth_term\n')
tot=cand=0; per={}
for f in sorted(glob.glob('data/articles/*.jsonl')):
    o=os.path.basename(f)[:-6]; n=c=0
    for l in open(f):
        d=json.loads(l)
        if d.get('status')!=200: continue
        n+=1
        s=((d.get('title') or '')+' \n '+(d.get('text') or '')[:1500]).lower()
        p=has(s,PROTEST)
        if p:
            c+=1; out.write(f"{o}\t{d['url']}\t{d.get('date') or d.get('listed_date')}\t1\t{int(has(s,YOUTH))}\n")
    per[o]=(n,c); tot+=n; cand+=c
print(tot,cand)
