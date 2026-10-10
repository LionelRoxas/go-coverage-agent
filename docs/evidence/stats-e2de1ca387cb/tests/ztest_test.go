package stats

import (
	"errors"
	"math"
	"testing"
)

func TestZTest(t *testing.T) {
	cases := []struct {
		name     string
		data1    Float64Data
		data2    Float64Data
		popMean  float64
		popStd   float64
		wantErr  error
		wantZ    float64
		wantP    float64
		checkNaN bool
	}{
		{
			name:    "EmptyInput",
			data1:   Float64Data{},
			data2:   nil,
			popMean: 0,
			popStd:  1,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "OneSample_BoundsError",
			data1:   Float64Data{1, 2, 3},
			data2:   nil,
			popMean: 0,
			popStd:  0,
			wantErr: ErrBounds,
		},
		{
			name:    "OneSample_Normal",
			data1:   Float64Data{1, 2, 3},
			data2:   nil,
			popMean: 2,
			popStd:  1,
			wantErr: nil,
		},
		{
			name:    "TwoSample_BoundsError",
			data1:   Float64Data{1, 2, 3},
			data2:   Float64Data{2, 3, 4},
			popMean: 0, // ignored
			popStd:  0,
			wantErr: ErrBounds,
		},
		{
			name:    "TwoSample_Normal",
			data1:   Float64Data{1, 2, 3},
			data2:   Float64Data{2, 3, 4},
			popMean: 0, // ignored
			popStd:  1,
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			z, p, err := ZTest(tc.data1, tc.data2, tc.popMean, tc.popStd)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			// Handle NaN expectations (none for current cases)
			if tc.checkNaN {
				if !math.IsNaN(z) || !math.IsNaN(p) {
					t.Fatalf("expected NaN results, got z=%v p=%v", z, p)
				}
				return
			}
			// Compute expected values for normal cases
			if tc.wantErr == nil {
				// One-sample case
				if tc.data2 == nil || len(tc.data2) == 0 {
					mean1, _ := Mean(tc.data1)
					n1 := float64(tc.data1.Len())
					se := tc.popStd / math.Sqrt(n1)
					tc.wantZ = (mean1 - tc.popMean) / se
				} else { // Two-sample case
					mean1, _ := Mean(tc.data1)
					mean2, _ := Mean(tc.data2)
					n1 := float64(tc.data1.Len())
					n2 := float64(tc.data2.Len())
					se := tc.popStd * math.Sqrt(1.0/n1+1.0/n2)
					tc.wantZ = (mean1 - mean2) / se
				}
				tc.wantP = 2 * NormSf(math.Abs(tc.wantZ), 0, 1)
			}
			if math.Abs(z-tc.wantZ) > 1e-9 {
				t.Fatalf("z mismatch: got %v want %v", z, tc.wantZ)
			}
			if math.Abs(p-tc.wantP) > 1e-9 {
				t.Fatalf("pvalue mismatch: got %v want %v", p, tc.wantP)
			}
		})
	}
}
