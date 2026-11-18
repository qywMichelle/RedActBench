"""Full non-anchor authored cases."""
from cases_medium import medium_cases
from case_recall import fridge_recall
from case_astronomy import astronomy
from cases_settlement import settlement_cases
from cases_distribution import distribution_cases
from cases_operations import operations_cases
from cases_closure import repair_report
from cases_coupled import network_coupled,laundry_coupled
from case_compost import compost
from medium_rights import extend_boardwalk,extend_parcel

def other_cases():
 medium=[extend_boardwalk(c) if c['short_id']=='t3-01' else extend_parcel(c) if c['short_id']=='t4-01' else c for c in medium_cases()]
 return medium+[fridge_recall(),astronomy()]+[settlement_cases()[0],network_coupled()]+distribution_cases()+[operations_cases()[0],laundry_coupled()]+[repair_report(),compost()]
