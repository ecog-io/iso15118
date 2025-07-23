from pydantic.v1 import BaseModel as PydanticBaseModel


class BaseModel(PydanticBaseModel):
    class Config:
        """
        Changing default pydantic configuration to suit our needs for handling
        the messages of the communication protocols DIN SPEC 70121 and ISO 15118
        """

        # Allow input by alias or field name
        allow_population_by_field_name = True

        # Forbid extra attributes during model initialization
        extra = "forbid"

        # Validate the field if it's set on an instance (e.g. a field like
        # response code is added after the Model has been instantiated)
        validate_assignment = True
