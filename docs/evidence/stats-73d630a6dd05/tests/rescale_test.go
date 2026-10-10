package stats

import (
	"errors"
	"math"
	"testing"
)

func TestRescale_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"zeroRange", Float64Data{5, 5, 5}, nil, ErrZero},
		{"normal", Float64Data{2, 4, 6}, []float64{0, 0.5, 1}, nil},
		{"negative", Float64Data{-2, 0, 2}, []float64{0, 0.5, 1}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Rescale(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if len(got) != len(tc.want) {
					t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
				}
				for i := range got {
					if math.Abs(got[i]-tc.want[i]) > 1e-9 {
						t.Fatalf("value mismatch at index %d: got %v, want %v", i, got[i], tc.want[i])
					}
				}
			}
		})
	}
}

func TestFloat64Data_Rescale_Method(t *testing.T) {
	// normal case
	data := Float64Data{10, 20}
	got, err := data.Rescale()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("expected 2 results, got %d", len(got))
	}
	if math.Abs(got[0]) > 1e-9 || math.Abs(got[1]-1) > 1e-9 {
		t.Fatalf("method result incorrect: %v", got)
	}

	// empty input should propagate ErrEmptyInput
	empty := Float64Data{}
	_, err = empty.Rescale()
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}
