#ifndef ENTERPRISE_EA_SETUP_ARBITRATION_MQH
#define ENTERPRISE_EA_SETUP_ARBITRATION_MQH

// G18 (design 2026-10-05-setup-arbitration-and-candidate-ledger): when several candidates
// compete in one timer pass, the live path visits them by evidence (G10) instead of engine
// order: S06 SWING, S04 SWING, S02 SWING, S04 SCALP, S02 SCALP. Pure: no broker access.

int EEA_SetupPriorityRank(const string setup,const string profile)
  {
   const int setup_rank=(setup=="S06" ? 0 : setup=="S04" ? 1 : 2);
   return (profile=="SWING" ? 0 : 3)+setup_rank;
  }

// order[] receives engine indices sorted by rank; equal ranks keep engine order (stable).
void EEA_SetupPriorityOrder(const string &setup[],const string &profile[],const int count,int &order[])
  {
   ArrayResize(order,count);
   for(int i=0;i<count;i++) order[i]=i;
   for(int i=1;i<count;i++)
     {
      const int v=order[i];
      const int rank=EEA_SetupPriorityRank(setup[v],profile[v]);
      int j=i-1;
      while(j>=0 && EEA_SetupPriorityRank(setup[order[j]],profile[order[j]])>rank) { order[j+1]=order[j]; j--; }
      order[j+1]=v;
     }
  }

#endif
