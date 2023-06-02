import numpy as np
import openclimate as oc
import pandas as pd

def actor_parts(actor_id: str, part_type: str='adm1') -> pd.DataFrame:
    """get the name and actor ID of all children of a parent actor ID
    
    Parameters
    ----------
    actor_id : str
        name of actor
    part_type : str (default: adm1)
        part type to look for

    Returns
    -------
    actor_parts : pd.DataFrame
        pandas dataframe with name and actor_id of parts
    """
    try:
        df_parts = (
            oc.Client()
            .parts(actor_id=actor_id, part_type=part_type)
            .loc[:, ['name', 'actor_id']]
            .reset_index(drop=True)
        )
        
        df_actor = (
            oc.Client()
            .search(query=actor_id)
            .loc[lambda x: x['actor_id']==actor_id, ['name', 'actor_id']]
        )
        
        return pd.concat([df_actor, df_parts])
    
    except AttributeError:
        print(f'ERROR: {actor_id} not found')
    except KeyError:
        print(f'{actor_id} does not have any {part_type} types')
        

def get_target(actor_id, year: int = 2030, data_id = None):
    """get target for actor_id
    
    Parameters
    ----------
    actor_id : str
        name of actor
    datasource_id: str 
        identifier for the datasource you want to pull from

    Returns
    -------
    df_emissions : pd.DataFrame
        pandas dataframe with emissions data 
    """
    #data_id = 'C2ES:canadian_GHG_targets' if data_id is None else data_id
    try:
        part_targets = (
            oc.Client().targets(actor_id = actor_id, ignore_warnings=True)
            .loc[lambda x: x['target_type'] == 'Absolute emission reduction', 
                 ['actor_id', 'baseline_year', 'target_year', 'target_value', 'target_unit', 'datasource_id']]
        ) 
        
        #part_target = part_targets.loc[part_targets['datasource_id']== data_id]
        
        closest_target = part_targets['target_year'][part_targets['target_year'] == year].min()
        cols_out = ['actor_id', 'baseline_year', 'target_year','target_value', 'target_unit']
        target = (
            part_targets
            .loc[part_targets['target_year'] == closest_target, cols_out]
            .drop_duplicates()
        )
        return target
    except:
        return None
    
    
def get_emissions(actor_id: str, datasource_id: str) -> pd.DataFrame:
    """get emission data for actor ID from particular datasource ID
    units of total_emissions is tonnes of CO2-equivalents 
    
    Parameters
    ----------
    actor_id : str
        name of actor
    datasource_id: str 
        identifier for the datasource you want to pull from

    Returns
    -------
    df_emissions : pd.DataFrame
        pandas dataframe with emissions data 
    """
    client = oc.Client()
    client.jupyter
    try:
        return client.emissions(actor_id=actor_id, datasource_id=datasource_id)
    except ValueError:
        return None
    
def ipcc_range(df, 
               actor_id: str = None, 
               baseline_year: int = 2019, 
               target_value15: float = 43, 
               target_value20: float = 27
) -> dict:
    """emissions required to be in line with AR6 
    1.5C : 43% reduction from 2019 levels by 2030
    2.0C : 27% reduction from 2019 levels by 2030
    
    Parameters
    ----------
    df : pd.dataframe
        dataframe with emissions
    actor_id: str 
        code for actor you want emissions from
        only relevant if multiple actors in the dataframe
    baseline_year : int
        baseline year for the targets (default: 2019)
    target_value15 : float
        target percent to meet 1.5C pathway (default: 43%)
    target_value20 : float
        target percent to meet 2.0C pathway (default: 27%)

    Returns
    -------
    dict_out : dict
        dictionary with inputs and target emissions in same units as df
        
    Source
    -------
    https://www.ipcc.ch/report/ar6/wg3/downloads/report/IPCC_AR6_WGIII_SPM.pdf
    see section C.1.1

    Notes
    -----
    PDF of source is here. https://www.ipcc.ch/site/assets/uploads/sites/2/2022/06/SPM_version_report_LR.pdf
    targets can be found in paragraph 2 of section 2.3.3.1
    """
    if actor_id is None:
        baseline_emissions = (
            df
            .loc[lambda x: x['year'] == baseline_year, 'total_emissions']
            .item()
        )
    else:
        baseline_emissions = (
            df
            .loc[lambda x: x['actor_id'] == actor_id]
            .loc[lambda x: x['year'] == baseline_year, 'total_emissions']
            .item() 
        )
        
    target_15 = baseline_emissions * (1 - target_value15/100)
    target_20 = baseline_emissions * (1 - target_value20/100)

    return {'baseline_year': baseline_year, 
            'target_value_1.5C': target_value15, 
            'target_emissions_1.5C': target_15,
            'target_value_2.0C': target_value20, 
            'target_emissions_2.0C': target_20,
           }

def linear_equation(baseline_year, baseline_emissions, target_percent, target_year):
    target_decimal = target_percent / 100
    target_emissions = baseline_emissions * (1 - target_decimal)
    d_emission = target_emissions - baseline_emissions
    d_year = target_year - baseline_year
    slope = d_emission / d_year
    intercept = baseline_emissions - slope * baseline_year
    equation = lambda YEAR: (slope * YEAR) + intercept
    return {'slope': slope, 'intercept': intercept, 'target_emissions': target_emissions, 'equation': equation}

def scaled_emissions(baseline_year, baseline_emissions, target_percent, target_year, scale_year):
    INPUTS_DICT = dict(
        baseline_year = baseline_year,
        baseline_emissions = baseline_emissions,
        target_percent = target_percent,
        target_year = target_year,
    )

    le = linear_equation(**INPUTS_DICT)

    return le['equation'](scale_year)