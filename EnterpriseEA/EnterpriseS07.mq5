// G94: EnterpriseS07, the live edition that trades the S07 family only (the same rules as S07Tester.mq5).
// It is EnterpriseEA.mq5 compiled with EEA_S07_EDITION, so every upgrade of the main EA applies here too:
// risk ledger, sessions, News Guard, sentiment, spread rule, trade manager and dashboard. The other
// setups, the drill and the AI bridge are constants (OFF) and absent from the Inputs dialog and the panel.
// It keeps its own data root (EnterpriseS07) and magic (707707); run one EA per account.
#define EEA_S07_EDITION
#include "EnterpriseEA.mq5"
