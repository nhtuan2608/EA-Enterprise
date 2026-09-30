#ifndef ENTERPRISE_EA_AUDIT_LOG_MQH
#define ENTERPRISE_EA_AUDIT_LOG_MQH

class CAuditLog
  {
private:
   int m_handle;
   string m_path;
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
