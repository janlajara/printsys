# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CutSheetSerializer
from estimation.utils import pack_rects, estimate_cuts


class FitSheetAPIView(APIView):

    def post(self, request, *args, **kwargs):
        serializer = CutSheetSerializer(data=request.data)
        if serializer.is_valid():
            # Access validated data
            cut_size = serializer.validated_data['cut_size']
            sheet_size = serializer.validated_data['sheet_size']

            cut_size_width = cut_size['width']
            cut_size_length = cut_size['length']
            sheet_size_width = sheet_size['width']
            sheet_size_length = sheet_size['length']

            cut_area = cut_size_width * cut_size_length
            sheet_area = sheet_size_width * sheet_size_length

            try:
                # Fit cut sizes inside the sheet size
                count, rects = pack_rects(
                    (sheet_size_width, sheet_size_length), 
                    (cut_size_width, cut_size_length))

                # Prepare layout information
                layout = []
                for rect in rects:
                    _, x, y, w, h, _ = rect
                    layout.append({"x": x, "y": y, "width": w, "length": h})

                result = {
                    "cut_size": cut_size,
                    "sheet_size": sheet_size,
                    "sheets_count": count, 
                    "waste": 1 - ((cut_area * count) / sheet_area),
                    "cuts_count": estimate_cuts(layout),
                    "layout": layout,
                }
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(result, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
