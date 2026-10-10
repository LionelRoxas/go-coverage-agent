package stats

import (
	"math"
	"testing"
)

func semApproxEqual(a, b float64) bool {
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= 1e-9
}

func TestSEM(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		wantErr error
		wantNaN bool
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			wantErr: ErrEmptyInput,
			wantNaN: true,
		},
		{
			name:  "non-empty input",
			input: Float64Data{2, 4, 4, 4, 5, 5, 7, 9},
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SEM(tc.input)
			if err != tc.wantErr {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			sd, _ := StandardDeviationSample(tc.input)
			expected := sd / math.Sqrt(float64(len(tc.input)))
			if !semApproxEqual(got, expected) {
				t.Fatalf("expected %v, got %v", expected, got)
			}
		})
	}
}

func TestFloat64Data_SEM(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		wantErr error
		wantNaN bool
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			wantErr: ErrEmptyInput,
			wantNaN: true,
		},
		{
			name:  "non-empty input",
			input: Float64Data{2, 4, 4, 4, 5, 5, 7, 9},
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.SEM()
			if err != tc.wantErr {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			sd, _ := StandardDeviationSample(tc.input)
			expected := sd / math.Sqrt(float64(len(tc.input)))
			if !semApproxEqual(got, expected) {
				t.Fatalf("expected %v, got %v", expected, got)
			}
		})
	}
}
