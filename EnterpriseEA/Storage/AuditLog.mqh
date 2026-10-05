#ifndef ENTERPRISE_EA_AUDIT_LOG_MQH
#define ENTERPRISE_EA_AUDIT_LOG_MQH

// NFR-07: the live file is archived as <dir>/<name>-YYYYMMDD-HHMMSS.jsonl (UTC) once it
// would pass EEA_AUDIT_ROTATE_BYTES; only the newest EEA_AUDIT_KEEP_ARCHIVES are kept.
// A failed rotation keeps appending to the current file: events are never dropped.
#define EEA_AUDIT_ROTATE_BYTES 20971520
#define EEA_AUDIT_KEEP_ARCHIVES 10

class CAuditLog
  {
private:
   int m_handle;
   string m_path;
   string Dir(void) const
     {
      int slash=-1;
      for(int i=StringLen(m_path)-1;i>=0;i--)
         if(StringGetCharacter(m_path,i)=='/') { slash=i; break; }
      return slash>=0 ? StringSubstr(m_path,0,slash+1) : "";
     }
   string Stem(void) const
     {
      string name=StringSubstr(m_path,StringLen(Dir()));
      int dot=StringFind(name,".jsonl");
      return dot>0 ? StringSubstr(name,0,dot) : name;
     }
   static string Stamp(const datetime t)
     {
      MqlDateTime d;
      TimeToStruct(t,d);
      return StringFormat("%04d%02d%02d-%02d%02d%02d",d.year,d.mon,d.day,d.hour,d.min,d.sec);
     }
   void PruneArchives(void)
     {
      string names[];
      int n=0;
      string found;
      long search=FileFindFirst(Dir()+Stem()+"-*.jsonl",found,0);
      if(search==INVALID_HANDLE) return;
      do { ArrayResize(names,n+1); names[n++]=found; } while(FileFindNext(search,found));
      FileFindClose(search);
      if(n<=EEA_AUDIT_KEEP_ARCHIVES) return;
      ArraySort(names);   // the UTC stamp sorts oldest first
      for(int i=0;i<n-EEA_AUDIT_KEEP_ARCHIVES;i++) FileDelete(Dir()+names[i],0);
     }
   void RotateIfFull(const int incoming)
     {
      if((long)FileSize(m_handle)+incoming<=EEA_AUDIT_ROTATE_BYTES) return;
      FileClose(m_handle);
      m_handle=INVALID_HANDLE;
      string archive=Dir()+Stem()+"-"+Stamp(TimeGMT())+".jsonl";
      bool moved=!FileIsExist(archive,0) && FileMove(m_path,0,archive,0);
      m_handle=FileOpen(m_path,FILE_READ|FILE_WRITE|FILE_BIN|FILE_SHARE_READ);
      if(m_handle==INVALID_HANDLE)
         m_handle=FileOpen(m_path,FILE_WRITE|FILE_BIN|FILE_SHARE_READ);
      if(m_handle!=INVALID_HANDLE) FileSeek(m_handle,0,SEEK_END);
      if(moved) PruneArchives();
     }
   bool RecoverIncompleteTail(void)
     {
      int h=FileOpen(m_path,FILE_READ|FILE_BIN|FILE_SHARE_READ);
      if(h==INVALID_HANDLE) return false;
      ulong size=FileSize(h);
      if(size==0) { FileClose(h); return true; }
      FileSeek(h,(long)(size-1),SEEK_SET);
      int last=FileReadInteger(h,CHAR_VALUE);
      if(last==10) { FileClose(h); return true; }
      long keep=0;
      for(long pos=(long)size-1;pos>=0;pos--)
        {
         FileSeek(h,pos,SEEK_SET);
         if(FileReadInteger(h,CHAR_VALUE)==10) { keep=pos+1; break; }
        }
      string temp=m_path+".recover.tmp";
      FileDelete(temp,0);
      int out=FileOpen(temp,FILE_WRITE|FILE_BIN);
      if(out==INVALID_HANDLE) { FileClose(h); return false; }
      FileSeek(h,0,SEEK_SET);
      long remaining=keep;
      uchar chunk[];
      if(ArrayResize(chunk,4096)!=4096)
        { FileClose(out); FileClose(h); FileDelete(temp,0); return false; }
      bool ok=true;
      while(remaining>0)
        {
         int wanted=(int)MathMin(4096,remaining);
         uint read=FileReadArray(h,chunk,0,wanted);
         if(read!=(uint)wanted || FileWriteArray(out,chunk,0,(int)read)!=read)
           { ok=false; break; }
         remaining-=wanted;
        }
      FileFlush(out);
      FileClose(out);
      FileClose(h);
      if(ok) ok=FileMove(temp,0,m_path,FILE_REWRITE);
      if(!ok) FileDelete(temp,0);
      return ok;
     }
public:
   CAuditLog(void) { m_handle=INVALID_HANDLE; m_path=""; }
   bool IsOpen(void) const { return m_handle!=INVALID_HANDLE; }
   bool Open(const string path)
     {
      m_path=path;
      if(FileIsExist(path,0) && !RecoverIncompleteTail()) return false;
      m_handle=FileOpen(path,FILE_READ|FILE_WRITE|FILE_BIN|FILE_SHARE_READ);
      if(m_handle==INVALID_HANDLE)
         m_handle=FileOpen(path,FILE_WRITE|FILE_BIN|FILE_SHARE_READ);
      if(m_handle==INVALID_HANDLE) return false;
      FileSeek(m_handle,0,SEEK_END);
      return true;
     }
   bool Append(EEAEvent &event,const string source)
     {
      if(!IsOpen()) return false;
      string line=EEAEvent_ToJson(event,source);
      uchar bytes[];
      string record=line+"\r\n";
      int count=StringToCharArray(record,bytes,0,WHOLE_ARRAY,CP_UTF8)-1;
      RotateIfFull(count);
      if(!IsOpen()) return false;
      uint n=0;
      if(count>0) n=FileWriteArray(m_handle,bytes,0,count);
      FileFlush(m_handle);
      return n==(uint)count;
     }
   void Close(void)
     {
      if(IsOpen()) FileClose(m_handle);
      m_handle=INVALID_HANDLE;
     }
  };

#endif
