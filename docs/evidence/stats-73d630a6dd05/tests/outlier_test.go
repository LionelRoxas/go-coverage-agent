package stats

import (
	"math"
	"testing"
)

func outlierSlicesEqual(a, b Float64Data) bool {
	if len(a) != len(b) {
		return false
	}
	const eps = 1e-9
	for i := range a {
		if math.Abs(a[i]-b[i]) > eps && !(math.IsNaN(a[i]) && math.IsNaN(b[i])) {
			return false
		}
	}
	return true
}

func TestQuartileOutliers_Empty(t *testing.T) {
	var empty Float64Data
	_, err := QuartileOutliers(empty)
	if err == nil {
		t.Fatalf("expected error for empty input, got nil")
	}
	if err != EmptyInputErr {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestQuartileOutliers_ExtremeOnly(t *testing.T) {
	data := Float64Data{5, 5, 5, 5, 5, 100}
	out, err := QuartileOutliers(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expectedExtreme := Float64Data{100}
	if !outlierSlicesEqual(out.Extreme, expectedExtreme) {
		t.Fatalf("expected extreme %v, got %v", expectedExtreme, out.Extreme)
	}
	if len(out.Mild) != 0 {
		t.Fatalf("expected no mild outliers, got %v", out.Mild)
	}
}

func TestQuartileOutliers_MildOutlier(t *testing.T) {
	// Data where the value 20 is a mild outlier (outside inner fence but inside outer fence)
	input := Float64Data{1, 2, 3, 4, 5, 8, 20}
	out, err := QuartileOutliers(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expectedMild := Float64Data{20}
	expectedExtreme := Float64Data{}
	if !outlierSlicesEqual(out.Mild, expectedMild) {
		t.Fatalf("mild outliers mismatch: got %v want %v", out.Mild, expectedMild)
	}
	if !outlierSlicesEqual(out.Extreme, expectedExtreme) {
		t.Fatalf("extreme outliers mismatch: got %v want %v", out.Extreme, expectedExtreme)
	}
}

func TestQuartileOutliers_SmallInputs(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		wantErr bool
		wantOut Outliers
	}{
		{"single", Float64Data{1.0}, true, Outliers{}},
		{"two", Float64Data{1.0, 2.0}, false, Outliers{nil, nil}},
		{"three", Float64Data{1.0, 2.0, 3.0}, false, Outliers{nil, nil}},
	}
	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := QuartileOutliers(tc.input)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !outlierSlicesEqual(got.Mild, tc.wantOut.Mild) || !outlierSlicesEqual(got.Extreme, tc.wantOut.Extreme) {
				t.Fatalf("unexpected outliers: got %+v, want %+v", got, tc.wantOut)
			}
		})
	}
}
