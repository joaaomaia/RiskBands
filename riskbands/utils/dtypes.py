# riskbands/utils/dtypes.py
from __future__ import annotations
import warnings, pandas as pd
from typing import List, Optional, Tuple


def search_dtypes(
    df: pd.DataFrame, 
    target_col: str = 'target', 
    limite_categorico: int = 50, 
    force_categorical: Optional[List[str]] = None, 
    verbose: bool = True, 
    remove_ids: bool = False,
    id_patterns: Optional[List[str]] = None,
    force_numeric: Optional[List[str]] = None,
) -> Tuple[List[str], List[str]]:
    """
    Identifica e classifica colunas numÃ©ricas e categÃ³ricas em um DataFrame.

    Funcionalidades:
    - Valida entradas e trata erros de forma robusta
    - ForÃ§a colunas especÃ­ficas como categÃ³ricas
    - Classifica automaticamente por tipo de dados e cardinalidade
    - Remove colunas de ID opcionalmente
    - Suporte a padrÃµes customizados para identificaÃ§Ã£o de IDs

    ParÃ¢metros:
    -----------
    df : pd.DataFrame
        DataFrame de entrada para anÃ¡lise
    target_col : str, default 'target'
        Nome da coluna target a ser excluÃ­da da anÃ¡lise
    limite_categorico : int, default 50
        MÃ¡ximo de valores Ãºnicos para considerar coluna object como categÃ³rica
    force_categorical : List[str], optional
        Lista de colunas que devem ser forÃ§adas como categÃ³ricas
    force_numeric : List[str], optional
        Lista de colunas que devem ser forÃ§adas como numericas
    verbose : bool, default True
        Se True, imprime detalhes das decisÃµes tomadas
    remove_ids : bool, default False
        Se True, remove colunas identificadas como IDs
    id_patterns : List[str], optional
        PadrÃµes para identificar colunas de ID (ex: ['_id', 'id_', 'codigo'])

    Retorna:
    --------
    Tuple[List[str], List[str]]
        Tupla contendo (colunas_numericas, colunas_categoricas)

    Raises:
    -------
    ValueError
        Se o DataFrame estiver vazio ou se target_col nÃ£o existir
    TypeError
        Se os tipos dos parÃ¢metros estiverem incorretos
    """
    
    # ValidaÃ§Ãµes iniciais
    if not isinstance(df, pd.DataFrame):
        raise TypeError("O parÃ¢metro 'df' deve ser um pandas DataFrame")
    
    if df.empty:
        raise ValueError("O DataFrame nÃ£o pode estar vazio")
    
    if not isinstance(target_col, str):
        raise TypeError("O parÃ¢metro 'target_col' deve ser uma string")
    
    if not isinstance(limite_categorico, int) or limite_categorico <= 0:
        raise ValueError("O parÃ¢metro 'limite_categorico' deve ser um inteiro positivo")
    
    # Verifica se target_col existe no DataFrame
    if target_col not in df.columns:
        available_cols = ", ".join(df.columns.tolist()[:10])  # Mostra apenas primeiras 10
        suffix = "..." if len(df.columns) > 10 else ""
        raise ValueError(
            f"Coluna target '{target_col}' nÃ£o encontrada no DataFrame. "
            f"Colunas disponÃ­veis: {available_cols}{suffix}"
        )
    
    # InicializaÃ§Ã£o de variÃ¡veis
    num_cols = []
    cat_cols = []
    ignored_cols = []
    
    # Tratamento de parÃ¢metros opcionais
    force_categorical = force_categorical or []
    force_numeric = force_numeric or []
    id_patterns = id_patterns or ['client_id', '_id', 'id_', 'codigo', 'key']
    
    # ValidaÃ§Ã£o do force_categorical
    if not isinstance(force_categorical, list):
        raise TypeError("O parÃ¢metro 'force_categorical' deve ser uma lista de strings")
    if not isinstance(force_numeric, list):
        raise TypeError("O parametro 'force_numeric' deve ser uma lista de strings")
    if not all(isinstance(col, str) for col in force_categorical):
        raise TypeError("O parametro 'force_categorical' deve ser uma lista de strings")
    if not all(isinstance(col, str) for col in force_numeric):
        raise TypeError("O parametro 'force_numeric' deve ser uma lista de strings")

    active_force_categorical = [col for col in force_categorical if col != target_col]
    active_force_numeric = [col for col in force_numeric if col != target_col]

    conflicts = sorted(set(active_force_numeric) & set(active_force_categorical))
    if conflicts:
        raise ValueError(
            "Colunas em conflito entre force_numeric e force_categorical: "
            f"{conflicts}. Remova cada coluna de uma das listas."
        )
    
    # Verifica se colunas em force_categorical existem
    missing_forced = [col for col in active_force_categorical if col not in df.columns]
    if missing_forced:
        warnings.warn(
            f"Colunas em force_categorical nÃ£o encontradas: {missing_forced}",
            UserWarning
        )
        active_force_categorical = [col for col in active_force_categorical if col in df.columns]

    missing_force_numeric = [col for col in active_force_numeric if col not in df.columns]
    if missing_force_numeric:
        warnings.warn(
            f"Colunas em force_numeric nao encontradas: {missing_force_numeric}",
            UserWarning
        )
        active_force_numeric = [col for col in active_force_numeric if col in df.columns]

    force_categorical_set = set(active_force_categorical)
    force_numeric_set = set(active_force_numeric)
    
    # Cria DataFrame sem a coluna target
    try:
        df_work = df.drop(columns=[target_col], errors='raise')
    except KeyError as e:
        raise ValueError(f"Erro ao remover coluna target: {e}")
    
    if verbose:
        print(f"Analisando {len(df_work.columns)} colunas (excluindo target '{target_col}')...")
        print("-" * 60)
    
    # AnÃ¡lise das colunas
    for col in df_work.columns:
        try:
            # Obter informaÃ§Ãµes bÃ¡sicas da coluna
            tipo = df_work[col].dtype
            non_null_count = df_work[col].count()
            total_count = len(df_work)
            missing_pct = ((total_count - non_null_count) / total_count) * 100
            
            # Forca colunas explicitamente marcadas como numericas
            if col in force_numeric_set:
                num_cols.append(col)
                if verbose:
                    print(f"'{col}' -> NUMERICA (forcada por force_numeric)")
                continue

            # ForÃ§a colunas explicitamente marcadas como categÃ³ricas
            if col in force_categorical_set:
                cat_cols.append(col)
                if verbose:
                    print(f"âœ“ '{col}' -> CATEGÃ“RICA (forÃ§ada)")
                continue
            
            # Verifica se Ã© coluna com muitos valores missing
            if missing_pct > 90:
                ignored_cols.append(col)
                if verbose:
                    print(f"âš  '{col}' -> IGNORADA ({missing_pct:.1f}% valores ausentes)")
                continue
            
            # ClassificaÃ§Ã£o por tipo de dados
            if pd.api.types.is_numeric_dtype(tipo):
                # Verifica se Ã© uma coluna ID numÃ©rica
                if remove_ids and _is_id_column(col, df_work[col], id_patterns):
                    ignored_cols.append(col)
                    if verbose:
                        print(f"ðŸ—‘ '{col}' -> REMOVIDA (identificada como ID)")
                else:
                    num_cols.append(col)
                    if verbose:
                        unique_count = df_work[col].nunique(dropna=True)
                        print(f"ðŸ“Š '{col}' -> NUMÃ‰RICA ({unique_count} valores Ãºnicos)")
            
            elif tipo == 'object' or pd.api.types.is_string_dtype(tipo):
                # Remove IDs textuais se solicitado
                if remove_ids and _is_id_column(col, df_work[col], id_patterns):
                    ignored_cols.append(col)
                    if verbose:
                        print(f"ðŸ—‘ '{col}' -> REMOVIDA (identificada como ID)")
                    continue
                
                unique_count = df_work[col].nunique(dropna=True)
                
                if unique_count <= limite_categorico:
                    cat_cols.append(col)
                    if verbose:
                        print(f"ðŸ· '{col}' -> CATEGÃ“RICA ({unique_count} categorias)")
                else:
                    ignored_cols.append(col)
                    if verbose:
                        print(f"âš  '{col}' -> IGNORADA (muitas categorias: {unique_count})")
            
            elif pd.api.types.is_bool_dtype(tipo):
                cat_cols.append(col)
                if verbose:
                    print(f"â˜‘ '{col}' -> CATEGÃ“RICA (booleana)")
            
            elif pd.api.types.is_datetime64_any_dtype(tipo):
                ignored_cols.append(col)
                if verbose:
                    print(f"ðŸ“… '{col}' -> IGNORADA (datetime)")
            
            else:
                ignored_cols.append(col)
                if verbose:
                    print(f"â“ '{col}' -> IGNORADA (tipo nÃ£o suportado: {tipo})")
        
        except Exception as e:
            ignored_cols.append(col)
            if verbose:
                print(f"âŒ '{col}' -> ERRO ao processar: {str(e)}")
            warnings.warn(f"Erro ao processar coluna '{col}': {str(e)}", UserWarning)
    
    # RemoÃ§Ã£o adicional de IDs se solicitado
    if remove_ids:
        num_cols, cat_cols = _remove_id_columns(num_cols, cat_cols, id_patterns, verbose)
    
    # RelatÃ³rio final
    if verbose:
        print("\n" + "="*60)
        print("RESUMO DA CLASSIFICAÃ‡ÃƒO:")
        print("="*60)
        
        print(f"\nðŸ“Š VARIÃVEIS NUMÃ‰RICAS ({len(num_cols)}):")
        if num_cols:
            for col in sorted(num_cols):
                print(f"   â€¢ {col}")
        else:
            print("   (nenhuma encontrada)")
        
        print(f"\nðŸ· VARIÃVEIS CATEGÃ“RICAS ({len(cat_cols)}):")
        if cat_cols:
            for col in sorted(cat_cols):
                print(f"   â€¢ {col}")
        else:
            print("   (nenhuma encontrada)")
        
        if ignored_cols:
            print(f"\nâš  COLUNAS IGNORADAS ({len(ignored_cols)}):")
            for col in sorted(ignored_cols):
                print(f"   â€¢ {col}")
        
        print(f"\nðŸ“ˆ ESTATÃSTICAS:")
        print(f"   â€¢ Total de colunas analisadas: {len(df_work.columns)}")
        print(f"   â€¢ Colunas numÃ©ricas: {len(num_cols)}")
        print(f"   â€¢ Colunas categÃ³ricas: {len(cat_cols)}")
        print(f"   â€¢ Colunas ignoradas: {len(ignored_cols)}")
        print(f"   â€¢ Taxa de utilizaÃ§Ã£o: {((len(num_cols) + len(cat_cols)) / len(df_work.columns) * 100):.1f}%")
    
    return num_cols, cat_cols


def _is_id_column(col_name: str, col_data: pd.Series, id_patterns: List[str]) -> bool:
    """
    Verifica se uma coluna Ã© provavelmente um ID baseado no nome e caracterÃ­sticas.
    
    ParÃ¢metros:
    -----------
    col_name : str
        Nome da coluna
    col_data : pd.Series
        Dados da coluna
    id_patterns : List[str]
        PadrÃµes para identificar IDs
    
    Retorna:
    --------
    bool
        True se a coluna for identificada como ID
    """
    col_lower = col_name.lower()
    
    # Verifica padrÃµes no nome
    name_match = any(pattern.lower() in col_lower for pattern in id_patterns)
    
    # Verifica caracterÃ­sticas dos dados
    unique_ratio = col_data.nunique() / len(col_data) if len(col_data) > 0 else 0
    high_uniqueness = unique_ratio > 0.95  # Mais de 95% de valores Ãºnicos
    
    return name_match or high_uniqueness


def _remove_id_columns(num_cols: List[str], cat_cols: List[str], 
                      id_patterns: List[str], verbose: bool) -> Tuple[List[str], List[str]]:
    """
    Remove colunas identificadas como IDs das listas de colunas numÃ©ricas e categÃ³ricas.
    
    ParÃ¢metros:
    -----------
    num_cols : List[str]
        Lista de colunas numÃ©ricas
    cat_cols : List[str]
        Lista de colunas categÃ³ricas
    id_patterns : List[str]
        PadrÃµes para identificar IDs
    verbose : bool
        Se True, imprime remoÃ§Ãµes
    
    Retorna:
    --------
    Tuple[List[str], List[str]]
        Tupla com listas atualizadas (num_cols, cat_cols)
    """
    original_num = len(num_cols)
    original_cat = len(cat_cols)
    
    # Remove IDs das colunas numÃ©ricas
    num_cols_filtered = []
    for col in num_cols:
        if not any(pattern.lower() in col.lower() for pattern in id_patterns):
            num_cols_filtered.append(col)
        elif verbose:
            print(f"ðŸ—‘ Removendo '{col}' das numÃ©ricas (padrÃ£o ID detectado)")
    
    # Remove IDs das colunas categÃ³ricas
    cat_cols_filtered = []
    for col in cat_cols:
        if not any(pattern.lower() in col.lower() for pattern in id_patterns):
            cat_cols_filtered.append(col)
        elif verbose:
            print(f"ðŸ—‘ Removendo '{col}' das categÃ³ricas (padrÃ£o ID detectado)")
    
    removed_count = (original_num + original_cat) - (len(num_cols_filtered) + len(cat_cols_filtered))
    if verbose and removed_count > 0:
        print(f"ðŸ“‹ Total de colunas ID removidas: {removed_count}")
    
    return num_cols_filtered, cat_cols_filtered


