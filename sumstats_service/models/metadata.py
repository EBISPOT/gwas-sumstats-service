from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import date
from enum import Enum


class EffectStatisticEnum(str, Enum):
    beta = 'beta'
    odds_ratio = 'odds_ratio'
    hazard_ratio = 'hazard_ratio'


class SampleMetadata(BaseModel):
    ancestryMethod: Optional[List[str]] = None
    caseControlStudy: Optional[bool] = None
    caseCount: Optional[int] = None
    controlCount: Optional[int] = None
    sampleAncestry: List[str] = None
    sampleSize: int = None

    @validator('ancestryMethod', 'sampleAncestry', pre=True)
    def split_str(cls, v):
        if isinstance(v, str):
            return v.split('|')
        return v

    @validator('caseControlStudy', pre=True)
    def str_to_bool(cls, v):
        if str(v).lower() in {'no', 'false', 'n'}:
            return False
        elif str(v).lower() in {'yes', 'true', 'y'}:
            return True
        else:
            return v


class SumStatsMetadata(BaseModel):
    GWASCatalogAPI: Optional[str] = None
    GWASID: str = None
    adjustedCovariates: Optional[List[str]] = None
    analysisSoftware: Optional[str] = None
    authorNotes: Optional[str] = None
    coordinateSystem: Optional[str] = None
    dataFileMd5sum: str = None
    dataFileName: str = None
    dateLastModified: date = None
    minorAlleleFreqLowerLimit: Optional[float] = None
    effectStatistic: Optional[EffectStatisticEnum] = None
    fileType: str = None
    genomeAssembly: str = None
    genotypingTechnology: List[str] = []
    harmonisationReference: Optional[str] = None
    hmCodeDefinition: Optional[dict] = None
    imputationPanel: Optional[str] = None
    imputationSoftware: Optional[str] = None
    isHarmonised: Optional[bool] = False
    isSorted: Optional[bool] = False
    ontologyMapping: Optional[List[str]] = None
    pvalueIsNegLog10: Optional[bool] = False
    samples: List[SampleMetadata] = []
    sex: Optional[str] = None
    traitDescription: List[str] = None

    @validator('genotypingTechnology', 'traitDescription', 'ontologyMapping', 'adjustedCovariates', pre=True)
    def split_str(cls, v):
        if isinstance(v, str):
            return v.split('|')
        return v

    @validator('isHarmonised', 'isSorted', 'pvalueIsNegLog10',
               pre=True)
    def str_to_bool(cls, v):
        if str(v).lower() in {'no', 'false', 'n'}:
            return False
        elif str(v).lower() in {'yes', 'true', 'y'}:
            return True
        else:
            return v

    class Config:
        use_enum_values = True  
