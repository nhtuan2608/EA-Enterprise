#ifndef ENTERPRISE_EA_ATOMIC_WRITER_MQH
#define ENTERPRISE_EA_ATOMIC_WRITER_MQH

void EEA_EnsureFolder(const string path)
  {
   // FolderCreate may report false when the directory already exists. Actual file
   // opens below provide the definitive writable/readable check.
   FolderCreate(path,0);
  }

bool EEA_WriteAtomicText(const string path,const string contents)
  {
   string temp=path+".tmp";
   FileDelete(temp,0); // Remove any leftover temp from an interrupted prior write.
   int h=FileOpen(temp,FILE_WRITE|FILE_BIN);
   if(h==INVALID_HANDLE) return false;
   uchar bytes[];
   int count=StringToCharArray(contents,bytes,0,WHOLE_ARRAY,CP_UTF8)-1;
   uint written=0;
   if(count>0) written=FileWriteArray(h,bytes,0,count);
   FileFlush(h);
   FileClose(h);
   if(written!=(uint)count)
     {
      FileDelete(temp,0);
      return false;
     }
   ResetLastError();
   if(!FileMove(temp,0,path,FILE_REWRITE))
     {
      FileDelete(temp,0);
      Print("Atomic rename failed for ",path," error=",GetLastError());
      return false;
     }
   return true;
  }

#endif
