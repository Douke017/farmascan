from fastapi import HTTPException, status


class LPNNotFoundException(HTTPException):
    def __init__(self, lpn_code: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Código LPN '{lpn_code}' no encontrado en el inventario.",
        )


class FileProcessingException(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error procesando archivo: {message}",
        )


class JobNotFoundException(HTTPException):
    def __init__(self, job_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job de procesamiento '{job_id}' no encontrado.",
        )
