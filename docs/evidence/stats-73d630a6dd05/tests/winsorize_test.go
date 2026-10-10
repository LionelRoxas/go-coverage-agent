package stats

import (
	"errors"
	"math"
	"testing"
)

func TestWinsorize(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		want    []float64
		wantErr error
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			percent: 0.1,
			want:    nil,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "percent negative",
			input:   Float64Data{1, 2, 3},
			percent: -0.1,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "percent too large",
			input:   Float64Data{1, 2, 3},
			percent: 0.5,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "percent NaN",
			input:   Float64Data{1, 2, 3},
			percent: math.NaN(),
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "zero percent copy",
			input:   Float64Data{3, 1, 4},
			percent: 0.0,
			want:    []float64{3, 1, 4},
			wantErr: nil,
		},
		{
			name:    "normal clamping",
			input:   Float64Data{10, 1, 5, 100, 50},
			percent: 0.2,
			want:    []float64{10, 5, 5, 50, 50},
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Winsorize(tc.input, tc.percent)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
			}
			for i := range got {
				if math.IsNaN(tc.want[i]) && math.IsNaN(got[i]) {
					continue
				}
				if got[i] != tc.want[i] {
					t.Fatalf("at index %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
			if tc.percent == 0.0 && len(got) > 0 {
				// ensure the returned slice is a copy, not the original backing array
				originalFirst := tc.input[0]
				got[0] = got[0] + 1
				if tc.input[0] != originalFirst {
					t.Fatalf("expected returned slice to be a copy, but input was modified")
				}
			}
		})
	}
}

func TestFloat64Data_Winsorize(t *testing.T) {
	input := Float64Data{10, 1, 5, 100, 50}
	percent := 0.2
	want, err := Winsorize(input, percent)
	if err != nil {
		t.Fatalf("setup Winsorize error: %v", err)
	}
	got, err := input.Winsorize(percent)
	if err != nil {
		t.Fatalf("method Winsorize error: %v", err)
	}
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	for i := range got {
		if got[i] != want[i] {
			t.Fatalf("at index %d: got %v, want %v", i, got[i], want[i])
		}
	}
}
